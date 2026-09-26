# Adapter contract, version 1

The core accepts a corpus's raw UTF-8 bytes and an observation envelope. The corpus declares the domain facts and applicable comparison; the adapter measures outcomes. This boundary is not an authenticity or adversarial attestation mechanism. A dishonest adapter can lie about its observations, and an incorrect corpus can encode an incorrect contract.

Here is a complete example for a simulator that removes expiry-due units at the end of integer day 4. Three old units are due, while two fresh ones must survive. This is an unsold retention check, so the aggregate expected quantity is two.

```python
import hashlib
import json
from expirycheck import case_digest, evaluate

case = {
    "case_id": "example/mixed-age",
    "kind": "retention",
    "day": 4,
    "expiry_rule": {"phase": "after_expiry", "comparison": "lte"},
    "cohorts": [
        {"cohort_id": "old", "quantity": 3, "expiry": 4},
        {"cohort_id": "fresh", "quantity": 2, "expiry": 6},
    ],
}
corpus_bytes = (json.dumps({"schema_version": 1, "cases": [case]}) + "\n").encode()
observations = {
    "schema_version": 1,
    "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
    "adapter": "example/1",
    "observations": [{
        "case_id": case["case_id"],
        "case_sha256": case_digest(case),
        "remaining_quantity": 2,  # Replace with a measured quantity.
        "sold_quantity": 0,      # Replace with measured sales.
        "error": None,
    }],
}
report = evaluate(corpus_bytes, observations)
assert report["passed"] == 1
```

`evaluate` returns `checked`, `passed`, `failed`, `errors`, and `cases` containing each case's status, violations, and derived eligibility. It requires every case exactly once. Missing/duplicate cases, unknown observation fields (including expected answers), changed hashes, invalid dates, and malformed quantities raise `ContractError`. An adapter exception can instead be supplied as a nonempty `error` string on a bound row; it becomes an error, not a semantic defect or pass. A retention row with nonzero sales is likewise an evidence/precondition error.

## Cases

All cases require `case_id`, `kind`, `day`, `expiry_rule`, and a nonempty `cohorts` list. Optional `metadata` is an object included in the case hash. A cohort has `cohort_id`, nonnegative integer `quantity`, and `expiry` (integer day, ISO date `YYYY-MM-DD`, or `null` for nonperishable). Non-null dates must use the same type as the checked day. Quantities cannot be booleans. `comparison: "lt"` means expiry strictly precedes day; `"lte"` also treats equality as expired. The phase declaration is mandatory and must match the check kind.

| Kind | Phase | Observation fields beyond case ID, hash and error | Limits |
|---|---|---|---|
| `retention` | `after_expiry` | `remaining_quantity`, `sold_quantity` | Unsold aggregate retention only. Cannot identify which units survived or prove every intermediate transfer. |
| `sales` | `before_sales` | `ordinary_sold_ids`, `expired_removed_ids`, `remaining_ids` | Each cohort represents one identifiable unit (`quantity: 1`). The three lists must partition all original units. |
| `sale_count` | `before_sales` | `ordinary_sold_quantity` | Only homogeneous eligibility is allowed. Checks a sales upper bound, not exact demand, disposal, or conservation. |

Identity `sales` cases also require `sales_policy` (`all_eligible`, `none`, or `eligible_subset`) and `cleanup_policy` (`all_expired` or `expired_subset`). These are fixture-specific requirements, not universal retail policies. `all_eligible` is appropriate for the included deliberately saturated demand fixture; use `eligible_subset` when demand is not controlled. Stock removal must be recorded by reason: do not count ordinary sales and intentional expired clearance together.

## Binding and source checks

The envelope requires `schema_version: 1`, `corpus_sha256`, `adapter`, and `observations`. Optional `metadata` can hold source provenance. SHA-256 covers raw corpus bytes, including whitespace. `case_digest` uses canonical JSON, including metadata, so key order does not change the case digest.

The core verifies corpus/case binding and observation coverage. The separate reproduction runner verifies source/patch bytes and records adapter digests. It is the adapter author's responsibility to establish that the measured fixture implements the declared facts, use the native boundary, and report unsupported cases as errors. The supplied Prosus adapter rejects changed day/cohort facts it cannot implement; the Retail adapter constructs its unit/date fixture from the declared inputs.

For your own simulator, create your own explicit corpus and adapter. Do not replace source pins or overwrite the released evidence and continue quoting the original results.
