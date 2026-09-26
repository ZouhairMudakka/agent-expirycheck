"""Measure the RetailBench component fixtures; the shared checker judges them.

The source runner verifies the selected tree before invoking this adapter in a
separate process. This adapter uses actual Inventory/SKU/Merchandise classes
with an authored product, passive review hook, and recording database hook.
It does not construct RetailEnvironment or make model/network requests.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import random
import sys

sys.dont_write_bytecode = True

from expirycheck import case_digest, load_corpus


class RecordingWriter:
    """Capture native records without the real SQLite database."""

    def __init__(self):
        self.sold_ids = []
        self.expired_ids = []
        self.sales = []
        self.return_rates = []
        self.returns = []

    def add_record(self, sku_id, record):
        self.sales.append(record)

    def update_lifecycle_sold(self, merch_id, price, day):
        self.sold_ids.append(merch_id)

    def update_lifecycle_expired(self, merch_id, day):
        self.expired_ids.append(merch_id)

    def add_return_rate(self, record):
        self.return_rates.append(record)

    def add_return(self, record):
        self.returns.append(record)


class PassiveReviewHook:
    """No demand adjustment or generated text; native refunds still execute."""

    def compute_sales_impact(self, sku, current_date):
        return 0.0

    def maybe_generate_review_for_merchandise(self, merchandise, date_obj):
        return None


SKU_ID = "AUTHORED-COHORT"
RECIPE = {
    "sku_id": SKU_ID, "category": "AUTHORED", "price": 10.0,
    "buy_price": 4.0, "quality_score": 5.0, "constant_attraction": 10.0,
    "sigma": 0.0, "promotion_days": 3, "capacity": 20,
    "python_random_seed": 123, "numpy_random_seed": 123,
    "category_attraction_aggregation": "power", "category_attraction_rho": 3.0,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_fixture(case):
    require(case["kind"] == "sales", "Retail adapter requires identity sales cases")
    require(case["expiry_rule"] == {"phase": "before_sales", "comparison": "lt"},
            "Retail fixture uses the native before-sales strict expiry boundary")
    fixture = case.get("metadata", {}).get("fixture")
    require(isinstance(fixture, dict), "Retail metadata.fixture is required")
    require(set(fixture) == {"unit_begin", "shelved", "customers", "prelude_day"},
            "Unsupported Retail fixture fields")
    require(type(fixture["shelved"]) is bool, "shelved must be a boolean")
    require(type(fixture["customers"]) is int and fixture["customers"] in (0, 100),
            "Frozen Retail fixtures use 0 or 100 customers")
    require(isinstance(fixture["unit_begin"], dict), "unit_begin must map cohort IDs to dates")
    require(set(fixture["unit_begin"]) == {unit["cohort_id"] for unit in case["cohorts"]},
            "unit_begin IDs must match cohort IDs")
    require(0 < len(case["cohorts"]) <= RECIPE["capacity"], "Fixture exceeds stock capacity")
    for unit in case["cohorts"]:
        require(unit["quantity"] == 1 and isinstance(unit["expiry"], str),
                "Retail component requires one dated unit per cohort")
        begin = date.fromisoformat(fixture["unit_begin"][unit["cohort_id"]])
        require(begin + timedelta(days=3) == date.fromisoformat(unit["expiry"]),
                "Authored Retail cohorts have three-day shelf life")
    if fixture["prelude_day"] is not None:
        require(date.fromisoformat(fixture["prelude_day"]) + timedelta(days=1) == date.fromisoformat(case["day"]),
                "Prelude must immediately precede the main step")
    return fixture


def measure_case(case, Inventory, SKU, Merchandise, np):
    fixture = read_fixture(case)
    sku = SKU(sku_id=SKU_ID, category=RECIPE["category"], init_price=RECIPE["price"],
              model_parameters={"alpha": math.log(RECIPE["constant_attraction"]), "beta": 0, "sigma": 0},
              description={}, promotion_day=RECIPE["promotion_days"])
    inventory = Inventory(capacity=RECIPE["capacity"])
    units = []
    for unit in case["cohorts"]:
        merchandise = Merchandise(
            sku=sku, begin_time=date.fromisoformat(fixture["unit_begin"][unit["cohort_id"]]),
            expired_time=date.fromisoformat(unit["expiry"]),
            supplier_id="AUTHORED-SUPPLIER", merch_id=unit["cohort_id"],
            quality_score=RECIPE["quality_score"], buy_price=RECIPE["buy_price"],
        )
        inventory.add_item(merchandise)
        units.append(merchandise)

    def remaining_ids():
        return [unit.merch_id for batch in inventory.items_by_sku.values() for unit in batch]

    def step(day, shelved, customers):
        random.seed(RECIPE["python_random_seed"])
        np.random.seed(RECIPE["numpy_random_seed"])
        writer = RecordingWriter()
        result = inventory.step(
            day, customers, {SKU_ID: sku}, writer,
            review_manager=PassiveReviewHook(), new_manager=None,
            shelf_sku_ids={SKU_ID} if shelved else set(),
            category_attraction_aggregation=RECIPE["category_attraction_aggregation"],
            category_attraction_rho=RECIPE["category_attraction_rho"],
        )
        return writer, result

    prelude = None
    if fixture["prelude_day"] is not None:
        writer, result = step(date.fromisoformat(fixture["prelude_day"]), False, 100)
        require(not writer.sold_ids and not writer.expired_ids,
                "Prelude changed the declared source cohorts")
        require(remaining_ids() == [unit["cohort_id"] for unit in case["cohorts"]],
                "Prelude lost or changed source identities")
        prelude = {"day": fixture["prelude_day"], "shelved": False, "customers": 100,
                   "ordinary_sold_ids": writer.sold_ids, "expired_removed_ids": writer.expired_ids,
                   "remaining_ids": remaining_ids(), "money_earned": result[0]}

    day = date.fromisoformat(case["day"])
    before_ids = remaining_ids()
    native_predicate_before = {unit.merch_id: unit.judge_expired(day) for unit in units}
    writer, result = step(day, fixture["shelved"], fixture["customers"])
    remaining = remaining_ids()
    accounted = writer.sold_ids + writer.expired_ids + remaining
    require(len(accounted) == len(set(accounted)) and set(accounted) == set(before_ids),
            "Native lifecycle records do not conserve source unit identities")
    sale_records = [record.to_dict() for record in writer.sales]
    require(sum(record["move"] for record in sale_records) == len(writer.sold_ids),
            "Native sale and lifecycle record quantities disagree")
    require(all(record["price"] == RECIPE["price"] for record in sale_records),
            "Native sale record price differs from the authored product")
    require(sum(result[2].values()) == len(writer.sold_ids), "Native sales summary disagrees with lifecycle records")
    require(sum(result[4].values()) == len(writer.expired_ids), "Native expiry summary disagrees with lifecycle records")

    observation = {
        "case_id": case["case_id"], "case_sha256": case_digest(case), "error": None,
        "ordinary_sold_ids": writer.sold_ids, "expired_removed_ids": writer.expired_ids,
        "remaining_ids": remaining,
    }
    evidence = {
        "case_id": case["case_id"], "day": case["day"], "fixture": fixture,
        "prelude": prelude, "native_expired_predicate_before": native_predicate_before,
        "ordinary_sale_records": sale_records, "sales_by_sku": result[2],
        "returns_by_sku": result[3], "expired_by_sku": result[4],
        "money_earned": result[0], "cost_of_goods_sold": result[6],
    }
    return observation, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args()
    corpus_bytes = args.corpus.read_bytes()
    corpus = load_corpus(corpus_bytes)
    cases = [case for case in corpus["cases"] if case["case_id"].startswith("retail/")]
    require(bool(cases), "Corpus has no Retail cases")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(args.output.parent.resolve() / "cache" / "matplotlib")
    source_tree = args.source_tree.resolve()
    sys.path.insert(0, str(source_tree))
    sys.path.insert(0, str(source_tree / "module"))
    import numpy as np
    from sku import SKU, Merchandise
    from module.inventory import Inventory

    observations, evidence_cases = [], []
    for case in cases:
        try:
            observation, evidence = measure_case(case, Inventory, SKU, Merchandise, np)
        except Exception as exc:
            observation = {"case_id": case["case_id"], "case_sha256": case_digest(case),
                           "error": f"{type(exc).__name__}: {exc}"}
            evidence = {"case_id": case["case_id"], "error": observation["error"]}
        observations.append(observation)
        evidence_cases.append(evidence)
    args.output.write_text(json.dumps({
        "observations": observations,
        "evidence": {
            "scope": "Authored RetailBench component fixtures; canonical power mode only; no full environment or model evaluation",
            "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
            "inventory_source_sha256": hashlib.sha256((source_tree / "module/inventory.py").read_bytes()).hexdigest(),
            "recipe": RECIPE,
            "dependencies": {name: version(name) for name in ["numpy", "pandas", "matplotlib"]},
            "cases": evidence_cases,
        },
    }, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
