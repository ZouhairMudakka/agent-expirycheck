"""Observe reachable public-tool stock flows; expirycheck decides correctness.

World mutations use the real Engine.tool_* methods and their normal time costs.
Snapshots branch an already reachable state, never inventing inventory. Reading
internal counters is an observation, not a claim about the MCP transport.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import sys

from expirycheck import case_digest, load_corpus


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args()
    corpus = load_corpus(args.corpus.read_bytes())
    cases = {c["case_id"]: c for c in corpus["cases"]}
    sys.path.insert(0, str(args.source_tree / "tasks/vending-bench/environment/sim-server"))
    from vending import config
    from vending.engine import Engine

    pid = "sandwich-cheese"
    slot = "AI-LOUNGE:SNACK:C1"
    traces, diagnostics, observations = {}, {}, []

    def call(engine, trace, tool, *positional, **named):
        day_before = engine.s["day"]
        response = getattr(engine, "tool_" + tool)(*positional, **named)
        trace.append({"tool": tool, "args": positional, "kwargs": named,
                      "day_before": day_before, "day_after": engine.s["day"],
                      "response": response})
        return response

    def advance(engine, trace, target):
        while engine.s["day"] < target and not engine.over:
            call(engine, trace, "wait_for_next_day")
        if engine.s["day"] != target:
            raise RuntimeError(f"Could not reach day {target}; world ended at {engine.s['day']}")

    def counts(engine, product=pid):
        depot = engine.s["storage"].get(product, {}).get("quantity", 0)
        machine = sum(row["quantity"] for row in engine.s["machine"].values()
                      if row.get("product_id") == product)
        return {"depot": depot, "machine": machine, "total": depot + machine}

    def emit(name, *, day, cohorts, kind="retention", **fields):
        case_id = "prosus/" + name
        case = cases[case_id]
        rule = {"phase": "after_expiry", "comparison": "lte"} if kind == "retention" else {
            "phase": "before_sales", "comparison": "lt"}
        # Bind declared facts to this actual public-tool recipe before attaching
        # a case digest. A changed corpus must not silently relabel this run.
        observed_inputs = [(cohort["quantity"], cohort["expiry"]) for cohort in case["cohorts"]]
        if (case["kind"], case["day"], case["expiry_rule"], observed_inputs) != (kind, day, rule, cohorts):
            raise RuntimeError(f"Public-tool fixture does not implement declared facts: {case_id}")
        observations.append({"case_id": case_id, "case_sha256": case_digest(case),
                             "error": None, **fields})

    def load(engine, trace, target_slot, product, quantity):
        response = call(engine, trace, "restock_machine", target_slot, product, quantity)
        if f"Loaded {quantity} x" not in response:
            raise RuntimeError("Required fixture transfer was not performed")

    initial = Engine.new(seed=99)
    setup = traces["setup"] = []
    response = call(initial, setup, "order_goods", "bakker-en-zoon", {pid: 40, "cola-500ml": 10})
    receipt = json.loads(response.split("\n\n[Day ", 1)[0])
    if "error" in receipt:
        raise RuntimeError(receipt)
    while not initial.s["storage"].get(pid) and not initial.over:
        call(initial, setup, "wait_for_next_day")
    observed_storage = call(initial, setup, "get_storage_inventory")
    expiries = re.findall(r"batch of \d+ expires day (\d+)", observed_storage)
    if expiries != ["16"] or counts(initial)["total"] != 40 or initial.s["day"] != 14:
        raise RuntimeError("Public receipt does not match frozen corpus: 40 units, expiry16, day14")
    checkpoint = copy.deepcopy(initial.s)

    def retention(name, operations, observation_day):
        engine = Engine(copy.deepcopy(checkpoint))
        trace = traces[name] = []
        operations(engine, trace)
        advance(engine, trace, observation_day)
        call(engine, trace, "get_storage_inventory")
        call(engine, trace, "get_machine_inventory", "AI-LOUNGE:SNACK")
        if engine.s["day"] != observation_day:
            raise RuntimeError("Observation tools crossed a day boundary")
        actual = counts(engine)
        diagnostics[name] = {"observation_day": observation_day, "counts": actual,
                             "units_sold": engine.s["units_sold"]}
        emit(name, day=observation_day - 1, cohorts=[(40, 16)],
             remaining_quantity=actual["total"], sold_quantity=engine.s["units_sold"])

    def aged_load(engine, trace):
        advance(engine, trace, 15)
        load(engine, trace, slot, pid, 8)

    def round_trip(engine, trace):
        aged_load(engine, trace)
        call(engine, trace, "clear_slot", slot)
        call(engine, trace, "get_storage_inventory")

    def top_up(engine, trace):
        load(engine, trace, slot, pid, 7)
        advance(engine, trace, 15)
        load(engine, trace, slot, pid, 1)

    # Morning E+1 observes the completed cleanup of E. E-day sales are allowed.
    retention("storage_expiry_control", lambda e, t: None, 17)
    retention("aged_load", aged_load, 17)
    retention("clear_to_depot", round_trip, 17)
    retention("top_up_same_cohort", top_up, 18)
    retention("no_top_up_control", lambda e, t: load(e, t, slot, pid, 7), 18)
    retention("before_expiry_control", aged_load, 15)

    nonperishable = Engine(copy.deepcopy(checkpoint))
    ntrace = traces["nonperishable_round_trip_control"] = []
    if counts(nonperishable, "cola-500ml")["total"] != 10:
        raise RuntimeError("Nonperishable receipt differs from frozen corpus")
    load(nonperishable, ntrace, "AI-LOUNGE:DRINKS:C1", "cola-500ml", 5)
    call(nonperishable, ntrace, "clear_slot", "AI-LOUNGE:DRINKS:C1")
    advance(nonperishable, ntrace, 17)
    emit("nonperishable_round_trip_control", day=16, cohorts=[(10, None)],
         remaining_quantity=counts(nonperishable, "cola-500ml")["total"],
         sold_quantity=nonperishable.s["units_sold"])

    seller = Engine(copy.deepcopy(checkpoint))
    strace = traces["sale_after_reported_expiry"] = []
    aged_load(seller, strace)
    advance(seller, strace, 17)
    call(seller, strace, "set_price", slot, 4.20)
    revenue_before, units_before = seller.s["gross_revenue"], seller.s["units_sold"]
    call(seller, strace, "wait_for_next_day")
    sold = seller.s["units_sold"] - units_before
    diagnostics["sale_after_reported_expiry"] = {
        "sale_day": 17, "ordinary_sold_quantity": sold,
        "synthetic_gross_revenue": round(seller.s["gross_revenue"] - revenue_before, 2),
        "currency": config.CURRENCY,
    }
    emit("sale_after_reported_expiry", day=17, cohorts=[(8, 16)], kind="sale_count",
         ordinary_sold_quantity=sold)

    # Two paid public orders arrive in reverse order on days12/13 at seed99.
    # Drain35 older units into other slots, leaving5old+5fresh in the target.
    mixed = Engine.new(seed=99)
    mtrace = traces["mixed_cohort_setup"] = []
    call(mixed, mtrace, "order_goods", "bakker-en-zoon", {pid: 40})
    advance(mixed, mtrace, 3)
    call(mixed, mtrace, "order_goods", "bakker-en-zoon", {pid: 40})
    advance(mixed, mtrace, 14)
    public_cohorts = call(mixed, mtrace, "get_storage_inventory")
    if sorted(map(int, re.findall(r"batch of 40 expires day (\d+)", public_cohorts))) != [15, 16]:
        raise RuntimeError("Mixed-cohort receipts do not match frozen corpus")
    for drain_slot, quantity in [("C2", 10), ("C3", 10), ("D1", 10), ("D2", 5)]:
        load(mixed, mtrace, "AI-LOUNGE:SNACK:" + drain_slot, pid, quantity)
    load(mixed, mtrace, slot, pid, 5)
    load(mixed, mtrace, slot, pid, 5)
    if mixed.s["day"] != 14:
        raise RuntimeError("Mixed-cohort setup crossed a day")
    mixed_checkpoint = copy.deepcopy(mixed.s)
    for name, day in [("mixed_old_expires_fresh_survives", 16), ("mixed_all_expire", 17)]:
        branch = Engine(copy.deepcopy(mixed_checkpoint))
        trace = traces[name] = []
        advance(branch, trace, day)
        emit(name, day=day - 1, cohorts=[(5, 15), (5, 16)],
             remaining_quantity=branch.s["machine"][slot].get("quantity", 0),
             sold_quantity=branch.s["units_sold"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"observations": observations, "evidence": {"seed": 99, "diagnostics": diagnostics, "traces": traces}}
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Observed {len(observations)} Prosus cases")


if __name__ == "__main__":
    main()
