"""Small, simulator-independent expiry checks; no demand or pricing model.

The corpus declares a checked phase and the native expiry comparison. The
checker trusts those declarations and the adapter's measurements, not any
adapter-supplied expected answer. Hashes detect mismatched inputs, not dishonest
measurements. Aggregate retention cannot identify which individual units remain.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any


class ContractError(ValueError):
    """The corpus or observations cannot support the declared check."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _object(value: Any, where: str) -> dict:
    _require(isinstance(value, dict), f"{where}: expected an object")
    return value


def _keys(value: dict, required: set[str], optional: set[str], where: str) -> None:
    _require(required <= value.keys(), f"{where}: missing {sorted(required - value.keys())}")
    _require(value.keys() <= required | optional,
             f"{where}: unknown fields {sorted(value.keys() - required - optional)}")


def _text(value: Any, where: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{where}: expected nonempty text")
    return value


def _quantity(value: Any, where: str) -> int:
    _require(type(value) is int and value >= 0, f"{where}: expected nonnegative integer")
    return value


def _day(value: Any, where: str) -> int | date:
    if type(value) is int:
        return value
    _require(isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)),
             f"{where}: expected integer day or ISO date YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"{where}: invalid ISO date") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode(raw: bytes, where: str) -> dict:
    _require(isinstance(raw, bytes), f"{where}: expected raw UTF-8 bytes")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=lambda value: _invalid_constant(value))
    except (ValueError, UnicodeError) as exc:
        raise ContractError(f"{where}: {exc}") from exc
    return _object(result, where)


def _invalid_constant(value: str) -> None:
    raise ContractError(f"non-JSON numeric constant: {value}")


def case_digest(case: dict) -> str:
    """Hash a case including optional metadata using canonical JSON encoding."""
    try:
        encoded = json.dumps(case, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ContractError(f"case cannot be encoded as JSON: {exc}") from exc
    return sha256(encoded).hexdigest()


def _expired(cohort: dict, day: int | date, comparison: str) -> bool:
    expiry = cohort["expiry"]
    if expiry is None:
        return False
    parsed = _day(expiry, "cohort expiry")
    return parsed <= day if comparison == "lte" else parsed < day


def _validate_case(case: Any, index: int) -> dict:
    where = f"cases[{index}]"
    case = _object(case, where)
    _keys(case, {"case_id", "kind", "day", "expiry_rule", "cohorts"},
          {"sales_policy", "cleanup_policy", "metadata"}, where)
    _text(case["case_id"], f"{where}.case_id")
    kind = case["kind"]
    _require(kind in ("retention", "sales", "sale_count"), f"{where}: unknown kind")
    day = _day(case["day"], f"{where}.day")
    rule = _object(case["expiry_rule"], f"{where}.expiry_rule")
    _keys(rule, {"phase", "comparison"}, set(), f"{where}.expiry_rule")
    phase = "after_expiry" if kind == "retention" else "before_sales"
    _require(rule["phase"] == phase, f"{where}: {kind} requires phase {phase}")
    _require(rule["comparison"] in ("lte", "lt"), f"{where}: unknown expiry comparison")
    _require(isinstance(case["cohorts"], list) and bool(case["cohorts"]),
             f"{where}.cohorts: expected nonempty list")
    ids = set()
    for i, cohort in enumerate(case["cohorts"]):
        cw = f"{where}.cohorts[{i}]"
        cohort = _object(cohort, cw)
        _keys(cohort, {"cohort_id", "quantity", "expiry"}, set(), cw)
        cohort_id = _text(cohort["cohort_id"], f"{cw}.cohort_id")
        _require(cohort_id not in ids, f"{where}: duplicate cohort ID {cohort_id}")
        ids.add(cohort_id)
        quantity = _quantity(cohort["quantity"], f"{cw}.quantity")
        if kind == "sales":
            _require(quantity == 1, f"{cw}: identity sales require unit cohorts (quantity=1)")
        if cohort["expiry"] is not None:
            expiry = _day(cohort["expiry"], f"{cw}.expiry")
            _require(type(expiry) is type(day), f"{cw}: expiry/day types differ")
    if "metadata" in case:
        _object(case["metadata"], f"{where}.metadata")
    if kind == "sales":
        _require(case.get("sales_policy") in ("all_eligible", "none", "eligible_subset"),
                 f"{where}: identity sales require an explicit sales_policy")
        _require(case.get("cleanup_policy") in ("all_expired", "expired_subset"),
                 f"{where}: identity sales require an explicit cleanup_policy")
    else:
        _require("sales_policy" not in case and "cleanup_policy" not in case,
                 f"{where}: sales/cleanup policies only apply to identity sales")
    if kind == "sale_count":
        eligibility = {_expired(c, day, rule["comparison"]) for c in case["cohorts"]}
        _require(len(eligibility) == 1,
                 f"{where}: sale_count cannot identify sales from mixed expiry eligibility")
    return case


def load_corpus(corpus_bytes: bytes) -> dict:
    """Parse and validate a v1 corpus without running observations."""
    corpus = _decode(corpus_bytes, "corpus")
    _keys(corpus, {"schema_version", "cases"}, {"metadata"}, "corpus")
    _require(type(corpus["schema_version"]) is int and corpus["schema_version"] == 1,
             "corpus: unsupported schema_version")
    _require(isinstance(corpus["cases"], list) and bool(corpus["cases"]),
             "corpus.cases: expected nonempty list")
    ids = set()
    for i, case in enumerate(corpus["cases"]):
        _validate_case(case, i)
        _require(case["case_id"] not in ids, f"duplicate case ID: {case['case_id']}")
        ids.add(case["case_id"])
    if "metadata" in corpus:
        _object(corpus["metadata"], "corpus.metadata")
    return corpus


def _id_list(value: Any, where: str) -> list[str]:
    _require(isinstance(value, list), f"{where}: expected list")
    for item in value:
        _text(item, where)
    return value


def _check(case: dict, row: dict) -> dict:
    kind = case["kind"]
    base = {"case_id", "case_sha256", "error"}
    fields = {"retention": {"remaining_quantity", "sold_quantity"},
              "sales": {"ordinary_sold_ids", "expired_removed_ids", "remaining_ids"},
              "sale_count": {"ordinary_sold_quantity"}}[kind]
    _keys(row, base, fields, case["case_id"])
    _require(row["error"] is None or isinstance(row["error"], str) and bool(row["error"].strip()),
             f"{case['case_id']}: error must be null or nonempty text")
    result = {"case_id": case["case_id"], "case_sha256": case_digest(case),
              "status": "pass", "violations": [], "derived": {}}
    if row["error"] is not None:
        result.update(status="error", error=row["error"])
        return result
    _require(fields <= row.keys(), f"{case['case_id']}: missing observation fields")
    violations = result["violations"]

    def violation(code: str, detail: str) -> None:
        violations.append({"code": code, "detail": detail})

    day = _day(case["day"], "day")
    expired = {c["cohort_id"] for c in case["cohorts"]
               if _expired(c, day, case["expiry_rule"]["comparison"])}
    eligible = {c["cohort_id"] for c in case["cohorts"]} - expired
    eligible_quantity = sum(c["quantity"] for c in case["cohorts"]
                            if c["cohort_id"] in eligible)
    if kind == "retention":
        remaining = _quantity(row["remaining_quantity"], "remaining_quantity")
        sold = _quantity(row["sold_quantity"], "sold_quantity")
        if sold:
            result.update(status="error", error="Sales occurred; unsold retention check is not applicable")
            violation("retention_precondition", result["error"])
            return result
        result["derived"] = {"remaining_quantity": eligible_quantity,
                             "scope": "aggregate retention of unsold source cohorts"}
        if remaining != eligible_quantity:
            violation("retention_quantity", f"Observed {remaining}; source facts imply {eligible_quantity}")
    elif kind == "sale_count":
        sold = _quantity(row["ordinary_sold_quantity"], "ordinary_sold_quantity")
        result["derived"] = {"maximum_eligible_sales": eligible_quantity,
                             "scope": "sale eligibility bound only; no cleanup or demand check"}
        if sold > eligible_quantity:
            violation("sale_quantity", f"Observed {sold} sales exceed {eligible_quantity} eligible units")
    else:
        sold_list = _id_list(row["ordinary_sold_ids"], "ordinary_sold_ids")
        removed_list = _id_list(row["expired_removed_ids"], "expired_removed_ids")
        remaining_list = _id_list(row["remaining_ids"], "remaining_ids")
        sold, removed = set(sold_list), set(removed_list)
        counts = Counter(sold_list + removed_list + remaining_list)
        known = eligible | expired
        unknown = counts.keys() - known
        missing = known - counts.keys()
        repeated = sorted(key for key, count in counts.items() if count != 1)
        if unknown or missing or repeated:
            violation("unit_accounting", f"Unknown={sorted(unknown)}, missing={sorted(missing)}, repeated={repeated}")
        if sold & expired:
            violation("expired_ordinary_sale", f"Expired units sold: {sorted(sold & expired)}")
        if removed & eligible:
            violation("premature_expiry_removal", f"Eligible units removed: {sorted(removed & eligible)}")
        if case["sales_policy"] == "all_eligible" and sold != eligible:
            violation("required_sales", f"Ordinary sales must equal eligible units {sorted(eligible)}")
        if case["sales_policy"] == "none" and sold:
            violation("unexpected_sale", "Declared no-sale control recorded ordinary sales")
        if case["cleanup_policy"] == "all_expired" and removed != expired:
            violation("required_cleanup", f"Expired removal must equal expired units {sorted(expired)}")
        result["derived"] = {"eligible_ids": sorted(eligible), "expired_ids": sorted(expired),
                             "scope": "identity sale eligibility, cleanup, and unit accounting"}
    if violations:
        result["status"] = "fail"
    return result


def evaluate(corpus_bytes: bytes, envelope: bytes | dict) -> dict:
    """Evaluate every corpus case; malformed or unbound input raises ContractError.

    A simulator exception is a result with status='error'. A measured contract
    violation is status='fail'. Neither counts as a pass. No observed case may
    be omitted, duplicated, or silently matched against a different corpus.
    """
    corpus = load_corpus(corpus_bytes)
    envelope = _decode(envelope, "observations") if isinstance(envelope, bytes) else envelope
    _object(envelope, "observations")
    _keys(envelope, {"schema_version", "corpus_sha256", "adapter", "observations"},
          {"metadata"}, "observations")
    _require(type(envelope["schema_version"]) is int and envelope["schema_version"] == 1,
             "observations: unsupported schema_version")
    digest = sha256(corpus_bytes).hexdigest()
    _require(envelope["corpus_sha256"] == digest, "observations: corpus SHA-256 mismatch")
    _text(envelope["adapter"], "observations.adapter")
    if "metadata" in envelope:
        _object(envelope["metadata"], "observations.metadata")
    _require(isinstance(envelope["observations"], list), "observations: expected list")
    rows = {}
    for row in envelope["observations"]:
        _object(row, "observation")
        _require("case_id" in row and "case_sha256" in row, "observation: missing case binding")
        cid = _text(row["case_id"], "observation.case_id")
        _require(cid not in rows, f"duplicate observation: {cid}")
        rows[cid] = row
    cases = {case["case_id"]: case for case in corpus["cases"]}
    _require(rows.keys() == cases.keys(),
             f"case coverage mismatch: missing={sorted(cases.keys() - rows.keys())}, "
             f"unexpected={sorted(rows.keys() - cases.keys())}")
    results = []
    for case in corpus["cases"]:
        row = rows[case["case_id"]]
        _require(row["case_sha256"] == case_digest(case),
                 f"{case['case_id']}: case SHA-256 mismatch")
        results.append(_check(case, row))
    counts = Counter(result["status"] for result in results)
    return {"schema_version": 1, "corpus_sha256": digest, "adapter": envelope["adapter"],
            "checked": len(results), "passed": counts["pass"],
            "failed": counts["fail"], "errors": counts["error"], "cases": results}
