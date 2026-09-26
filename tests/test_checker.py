"""Adversarial checks for the independent oracle and evidence boundary."""

from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from expirycheck import ContractError, case_digest, evaluate, load_corpus


def cohort(cid="source", quantity=5, expiry=3):
    return {"cohort_id": cid, "quantity": quantity, "expiry": expiry}


def retention(day=3, cohorts=None, comparison="lte"):
    return {"case_id": "neutral/retention", "kind": "retention", "day": day,
            "expiry_rule": {"phase": "after_expiry", "comparison": comparison},
            "cohorts": cohorts if cohorts is not None else [cohort()]}


def sales(day="2026-01-05", cohorts=None, policy="all_eligible", cleanup="all_expired"):
    return {"case_id": "neutral/sales", "kind": "sales", "day": day,
            "expiry_rule": {"phase": "before_sales", "comparison": "lt"},
            "cohorts": cohorts if cohorts is not None else [
                cohort("old", 1, "2026-01-04"), cohort("fresh", 1, "2026-01-06")],
            "sales_policy": policy, "cleanup_policy": cleanup}


def count_case(day=4, cohorts=None):
    return {"case_id": "neutral/count", "kind": "sale_count", "day": day,
            "expiry_rule": {"phase": "before_sales", "comparison": "lt"},
            "cohorts": cohorts if cohorts is not None else [cohort()]}


def evidence(cases, measurements):
    raw = json.dumps({"schema_version": 1, "cases": cases}).encode("utf-8")
    rows = [{"case_id": case["case_id"], "case_sha256": case_digest(case),
             "error": None, **measurement} for case, measurement in zip(cases, measurements)]
    return raw, {"schema_version": 1, "corpus_sha256": sha256(raw).hexdigest(),
                 "adapter": "authored-test-observer", "observations": rows}


class CheckerTests(unittest.TestCase):
    def result(self, case, measurement):
        return evaluate(*evidence([case], [measurement]))["cases"][0]

    def test_expiry_equality_is_declared_not_universal(self):
        observation = {"remaining_quantity": 0, "sold_quantity": 0}
        self.assertEqual(self.result(retention(), observation)["status"], "pass")
        self.assertEqual(self.result(retention(comparison="lt"), observation)["status"], "fail")

    def test_before_expiry_requires_stock_retained(self):
        self.assertEqual(self.result(retention(day=2),
                                    {"remaining_quantity": 5, "sold_quantity": 0})["status"], "pass")
        self.assertEqual(self.result(retention(day=2),
                                    {"remaining_quantity": 0, "sold_quantity": 0})["status"], "fail")

    def test_mixed_retention_catches_renewal_and_discard_everything(self):
        case = retention(cohorts=[cohort("old", 5, 3), cohort("fresh", 7, 4)])
        for remaining, status in [(7, "pass"), (12, "fail"), (0, "fail")]:
            with self.subTest(remaining=remaining):
                result = self.result(case, {"remaining_quantity": remaining, "sold_quantity": 0})
                self.assertEqual(result["status"], status)
                self.assertEqual(result["derived"]["remaining_quantity"], 7)

    def test_nonperishable_is_never_expired(self):
        result = self.result(retention(day=999, cohorts=[cohort(expiry=None)]),
                             {"remaining_quantity": 5, "sold_quantity": 0})
        self.assertEqual(result["status"], "pass")

    def test_retention_requires_sales_free_precondition(self):
        result = self.result(retention(), {"remaining_quantity": 0, "sold_quantity": 1})
        self.assertEqual(result["status"], "error")
        self.assertIn("retention_precondition", [v["code"] for v in result["violations"]])

    def test_date_retention_uses_actual_calendar_order(self):
        case = retention(day="2026-01-01", cohorts=[cohort(expiry="2025-12-31")])
        self.assertEqual(self.result(case, {"remaining_quantity": 0, "sold_quantity": 0})["status"], "pass")

    def test_sales_mixed_correct_observation(self):
        result = self.result(sales(), {"ordinary_sold_ids": ["fresh"],
                                      "expired_removed_ids": ["old"], "remaining_ids": []})
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["derived"]["eligible_ids"], ["fresh"])

    def test_expired_ordinary_sale_is_failure(self):
        result = self.result(sales(), {"ordinary_sold_ids": ["old", "fresh"],
                                      "expired_removed_ids": [], "remaining_ids": []})
        self.assertEqual(result["status"], "fail")
        self.assertIn("expired_ordinary_sale", [v["code"] for v in result["violations"]])

    def test_date_equality_remains_eligible_for_strict_comparison(self):
        case = sales(day="2026-01-04", cohorts=[cohort("unit", 1, "2026-01-04")])
        result = self.result(case, {"ordinary_sold_ids": ["unit"],
                                   "expired_removed_ids": [], "remaining_ids": []})
        self.assertEqual(result["status"], "pass")

    def test_always_refuse_fails_positive_control(self):
        result = self.result(sales(), {"ordinary_sold_ids": [],
                                      "expired_removed_ids": ["old"], "remaining_ids": ["fresh"]})
        self.assertEqual(result["status"], "fail")
        self.assertIn("required_sales", [v["code"] for v in result["violations"]])

    def test_all_discard_fails_fresh_sale_control(self):
        result = self.result(sales(), {"ordinary_sold_ids": [],
                                      "expired_removed_ids": ["old", "fresh"], "remaining_ids": []})
        self.assertIn("premature_expiry_removal", [v["code"] for v in result["violations"]])

    def test_no_demand_control_requires_cleanup_without_sale(self):
        case = sales(policy="none")
        correct = {"ordinary_sold_ids": [], "expired_removed_ids": ["old"], "remaining_ids": ["fresh"]}
        self.assertEqual(self.result(case, correct)["status"], "pass")
        wrong = {"ordinary_sold_ids": [], "expired_removed_ids": [], "remaining_ids": ["old", "fresh"]}
        self.assertEqual(self.result(case, wrong)["status"], "fail")

    def test_eligible_subset_makes_no_demand_prediction(self):
        result = self.result(sales(policy="eligible_subset", cleanup="expired_subset"),
                             {"ordinary_sold_ids": [], "expired_removed_ids": [],
                              "remaining_ids": ["old", "fresh"]})
        self.assertEqual(result["status"], "pass")

    def test_unit_accounting_rejects_duplicate_unknown_missing_and_overlap(self):
        measurements = [
            {"ordinary_sold_ids": ["fresh", "fresh"], "expired_removed_ids": ["old"], "remaining_ids": []},
            {"ordinary_sold_ids": ["fresh"], "expired_removed_ids": ["old"], "remaining_ids": ["unknown"]},
            {"ordinary_sold_ids": ["fresh"], "expired_removed_ids": [], "remaining_ids": []},
            {"ordinary_sold_ids": ["fresh"], "expired_removed_ids": ["old"], "remaining_ids": ["fresh"]},
        ]
        for measurement in measurements:
            with self.subTest(measurement=measurement):
                result = self.result(sales(), measurement)
                self.assertIn("unit_accounting", [v["code"] for v in result["violations"]])

    def test_count_sale_bound_is_narrow(self):
        self.assertEqual(self.result(count_case(), {"ordinary_sold_quantity": 1})["status"], "fail")
        self.assertEqual(self.result(count_case(), {"ordinary_sold_quantity": 0})["status"], "pass")
        self.assertEqual(self.result(count_case(day=3), {"ordinary_sold_quantity": 4})["status"], "pass")
        self.assertEqual(self.result(count_case(day=3), {"ordinary_sold_quantity": 6})["status"], "fail")

    def test_count_sales_refuses_mixed_eligibility(self):
        case = count_case(cohorts=[cohort("old", 2, 3), cohort("fresh", 2, 5)])
        with self.assertRaisesRegex(ContractError, "mixed expiry eligibility"):
            evidence_raw, _ = evidence([case], [])
            load_corpus(evidence_raw)

    def test_simulator_exception_is_error_not_semantic_failure(self):
        result = self.result(retention(), {"error": "Simulator did not reach the requested phase"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["violations"], [])

    def test_wrong_corpus_hash_rejected(self):
        raw, envelope = evidence([retention()], [{"remaining_quantity": 0, "sold_quantity": 0}])
        with self.assertRaisesRegex(ContractError, "corpus SHA-256"):
            evaluate(raw + b"\n", envelope)

    def test_changed_case_hash_rejected(self):
        raw, envelope = evidence([retention()], [{"remaining_quantity": 0, "sold_quantity": 0}])
        envelope["observations"][0]["case_sha256"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "case SHA-256"):
            evaluate(raw, envelope)

    def test_case_digest_includes_recipe_metadata_and_is_key_order_independent(self):
        case = retention()
        self.assertEqual(case_digest(case), case_digest(dict(reversed(list(case.items())))))
        altered = copy.deepcopy(case)
        altered["metadata"] = {"recipe": "different"}
        self.assertNotEqual(case_digest(case), case_digest(altered))

    def test_full_coverage_required(self):
        raw, envelope = evidence([retention()], [{"remaining_quantity": 0, "sold_quantity": 0}])
        for mutate in (lambda rows: rows.clear(), lambda rows: rows[0].update(case_id="unknown"),
                       lambda rows: rows.append(copy.deepcopy(rows[0]))):
            changed = copy.deepcopy(envelope)
            mutate(changed["observations"])
            with self.assertRaises(ContractError):
                evaluate(raw, changed)

    def test_duplicate_case_and_cohort_ids_rejected(self):
        for cases in ([retention(), retention()],
                      [retention(cohorts=[cohort(), cohort()])]):
            with self.assertRaises(ContractError):
                load_corpus(evidence(cases, [])[0])

    def test_boolean_quantities_are_not_integers(self):
        with self.assertRaises(ContractError):
            self.result(retention(cohorts=[cohort(quantity=True)]),
                        {"remaining_quantity": 0, "sold_quantity": 0})
        for key in ("remaining_quantity", "sold_quantity"):
            row = {"remaining_quantity": 0, "sold_quantity": 0, key: False}
            with self.assertRaises(ContractError):
                self.result(retention(), row)
        with self.assertRaises(ContractError):
            self.result(count_case(), {"ordinary_sold_quantity": False})

    def test_invalid_dates_mixed_types_and_boolean_days_rejected(self):
        cases = [retention(day="2026-02-30"), retention(day="20260101"), retention(day=True),
                 retention(day="2026-01-01"), retention(cohorts=[cohort(expiry=False)])]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ContractError):
                load_corpus(evidence([case], [])[0])

    def test_bad_contracts_rejected(self):
        cases = []
        for field, value in [("kind", "unknown"), ("unexpected", 2)]:
            changed = retention()
            changed[field] = value
            cases.append(changed)
        for field, value in [("phase", "before_sales"), ("comparison", "approximately")]:
            changed = retention()
            changed["expiry_rule"][field] = value
            cases.append(changed)
        cases.extend([retention(cohorts=[cohort(quantity=-1)]),
                      sales(cohorts=[cohort("unit", 2, "2026-01-01")]),
                      sales(policy="predict_demand")])
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ContractError):
                load_corpus(evidence([case], [])[0])

    def test_missing_observation_field_and_expected_answer_rejected(self):
        for row in ({"sold_quantity": 0},
                    {"remaining_quantity": 0, "sold_quantity": 0, "expected": 0}):
            with self.assertRaises(ContractError):
                self.result(retention(), row)

    def test_json_duplicate_keys_and_nan_rejected(self):
        for raw in (b'{"schema_version":1,"schema_version":1,"cases":[]}',
                    b'{"schema_version":NaN,"cases":[]}'):
            with self.assertRaises(ContractError):
                load_corpus(raw)

    def test_json_observation_bytes_and_report_counts(self):
        first, second = retention(), count_case()
        raw, envelope = evidence([first, second], [
            {"remaining_quantity": 0, "sold_quantity": 0}, {"ordinary_sold_quantity": 1}])
        report = evaluate(raw, json.dumps(envelope).encode())
        self.assertEqual({key: report[key] for key in ("checked", "passed", "failed", "errors")},
                         {"checked": 2, "passed": 1, "failed": 1, "errors": 0})

    def test_release_corpus_validates_and_is_not_an_outcome_table(self):
        path = Path(__file__).resolve().parents[1] / "corpus" / "cases.json"
        corpus = load_corpus(path.read_bytes())
        self.assertEqual(len(corpus["cases"]), 18)
        self.assertEqual(sum(c["kind"] == "retention" for c in corpus["cases"]), 9)
        self.assertEqual(sum(c["kind"] == "sales" for c in corpus["cases"]), 8)
        self.assertEqual(sum(c["kind"] == "sale_count" for c in corpus["cases"]), 1)
        for case in corpus["cases"]:
            self.assertNotIn("expected", case)
            self.assertNotIn("pass", case)


if __name__ == "__main__":
    unittest.main()
