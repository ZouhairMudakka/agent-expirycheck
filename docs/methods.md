# Method and retained observations

`agent-expirycheck` checks whether dated inventory remains consistent with an explicitly declared expiry contract. Its contribution is a reproducible corpus covering two public implementations, source-bound observations, and diagnostic corrections. The checker does not simulate demand, pricing, or agent behavior. See [prior art](prior-art.md) and [limits](limits.md) for the scope of this claim.

## Sources and pins

| Implementation | Tested source | Evidence boundary |
|---|---|---|
| Prosus Vending Bench | [`ProsusAI/vending-bench`](https://github.com/ProsusAI/vending-bench/tree/f9a1d7efde193de2242ed5afb1f3a326e362c75d), commit `f9a1d7efde193de2242ed5afb1f3a326e362c75d` | In-process public business-tool methods, real supported catalogue goods, normal tool time |
| RetailBench | [Anonymized release `RetailBench_ARR-6253`](https://anonymous.4open.science/r/RetailBench_ARR-6253/README.md), retrieved 26–27 September 2026 | Released inventory component with authored products and small hooks |

The [Prosus manifest](../third_party/prosus-manifest.json) and [Retail manifest](../third_party/retail-manifest.json) identify the selected original files and their SHA-256 hashes. RetailBench's viewer exposes no immutable Git commit; the downloaded bytes, not a viewer query parameter, are the pin. Its original `module/inventory.py` hash is `c31fb1af43ac6cb2fa803ddb66a3b5fbaf18a8a34e1718e9d8f1f46a944bfd12`. The reproduction checks the manifests before running source copies and applies separate, hashed [Prosus](../patches/prosus.patch) and [Retail](../patches/retail.patch) patches to corrected copies.

## Contract, phase, and oracle

The [corpus](../corpus/cases.json) declares original cohort quantities and expiry dates, a checked day, an observation phase, and the native expiry comparison. A date is insufficient without its phase:

| Implementation/check | Rule preserved by this experiment |
|---|---|
| Prosus retention | After day `D`'s expiry cleanup, cohorts with `expiry <= D` are due for removal. This phase is usually observed on the following morning. |
| Prosus ordinary sale | Sales on expiry day `E` precede its end-of-day cleanup and remain allowed. The adverse sale case is on `E + 1`. |
| Retail ordinary sale | The native `judge_expired(day)` is true when `day > expiry`. Equality on the expiry date remains eligible. |

The Prosus contract is that moving or topping up unchanged stock preserves its previously reported expiry. That is a stated domain assumption supported by the tool's description of returning goods, warehouse batch dates, and absence of a modeled preservation treatment. It is not a universal physical shelf-life law. Retail's oracle checks the implementation's own expired predicate before ordinary sale and distinguishes ordinary sales from its separate expired-stock cleanup.

The checker derives permitted outcomes from those original facts; adapters supply measurements, not expected answers. Three observation forms have deliberately different strength:

- **Retention:** in a sales-free case, remaining quantity must equal the sum of cohorts not yet due. This is an aggregate check; it cannot establish which individual units remain.
- **Sale count:** ordinary sales cannot exceed eligible quantity. This form refuses mixed expiry eligibility because a count cannot identify the sold cohort. It does not check demand or cleanup.
- **Unit-identified sales:** every unit must occur exactly once among ordinary sales, expiry removals, and remaining inventory. Expired units cannot enter ordinary sales; fresh units cannot be removed as expired. Explicit fixture policies determine whether all eligible units must sell and all expired units must be cleared.

Corpus and per-case hashes bind observations to the inputs being checked. Missing cases, duplicated observations, malformed contracts, and input mismatches are rejected; simulator errors are distinct from measured violations. Hashes do not prove that measurements are truthful. Paired waiting/movement and old/fresh cases express familiar metamorphic relations, while absolute cohort expectations also prevent two equally wrong implementations from passing merely by agreement.

## Prosus fixtures

Starting with the actual engine at seed 99, public ordering and waiting operations obtain the catalogue's three-day-life `sandwich-cheese`. Receipt and expiry evidence comes from public storage inventory output. Reachable checkpoints are copied into comparison branches; stock is not injected into the public-operation cases. Most slots remain unpriced so no sales occur while age preservation is isolated. Normal tool durations remain charged, and diagnostic reads avoid closing-time ambiguity.

The mixed fixture orders two 40-unit cohorts on days 1 and 3. In this seed they arrive on days 13 and 12, with expiry days 16 and 15. On day 14, ordinary restocking moves 35 older units to other slots, then puts five older and five newer units together in the target slot. The required target totals are five after the older cohort's cleanup and zero after both cohorts' cleanup. This rejects both lifetime renewal and a whole-slot earliest-expiry correction that discards fresh stock prematurely.

## Retail fixtures

The released `Inventory`, `SKU`, `Merchandise`, sale-record, and refund model code runs on an authored one-SKU fixture. It uses one or two units, price 10, acquisition cost 4, three-day shelf life, constant attraction, and zero SKU noise. Python and NumPy are seeded before each step; actual binomial/multinomial demand sampling runs. A passive review hook provides zero attraction adjustment and no review text; a recording writer captures production record calls instead of using SQLite.

The two-day fixture calls `Inventory.step` on consecutive dates, first off shelf on expiry day and then on shelf the next day. Evidence includes the native expired predicate; the independent checker derives eligibility from the original dates and tracks unit IDs. The initial reproduction also cross-checked that date comparison against the native predicate. Ample-demand fresh-stock controls and complete expiry cleanup checks prevent a correction that simply suppresses all sales or discards all stock from passing. Only `power` demand mode is validated.

## Observed case matrix

These are deliberately chosen regression cases, not independent random samples. All corrected cases pass the same declared contract.

| Family / case ID suffix | Original | Corrected |
|---|---|---|
| Prosus `storage_expiry_control` | Pass | Pass |
| Prosus `aged_load` | Fail | Pass |
| Prosus `clear_to_depot` | Fail | Pass |
| Prosus `top_up_same_cohort` | Fail | Pass |
| Prosus `no_top_up_control` | Pass | Pass |
| Prosus `before_expiry_control` | Pass | Pass |
| Prosus `nonperishable_round_trip_control` | Pass | Pass |
| Prosus `sale_after_reported_expiry` | Fail | Pass |
| Prosus `mixed_old_expires_fresh_survives` | Fail | Pass |
| Prosus `mixed_all_expire` | Fail | Pass |
| Retail `before-expiry` | Pass | Pass |
| Retail `at-expiry` | Pass | Pass |
| Retail `after-expiry` | Fail | Pass |
| Retail `unshelved-then-shelved` | Fail | Pass |
| Retail `expired-unshelved-cleanup` | Pass | Pass |
| Retail `expired-zero-demand-cleanup` | Pass | Pass |
| Retail `mixed-expiry-cohorts` | Fail | Pass |
| Retail `fresh-after-old-boundary` | Pass | Pass |

The original passes 9/18 cases; the diagnostic corrections pass 18/18. The nine failures belong to **two defect families**: loss of stock age during Prosus transitions, and Retail ordinary-sale eligibility ignoring already-expired units. They are not nine independent discoveries or an estimated failure rate.

The Prosus expired-sale case records two units and EUR 8.40 gross revenue in the original, versus zero after correction. Retail's mixed fixture records two ordinary sales for amount 20 originally, versus one fresh-unit sale for amount 10 and one expired cleanup after correction. These are synthetic fixture observations, not profit estimates.

The unchanged Prosus engine suite passes 58 tests despite the six corpus violations. Its corrected copy passes those 58 plus nine focused cohort regression tests. Those additional unit tests use direct receipt/clock fixtures and controlled sale counts; they are separate from the ten public-operation cases. No Retail native regression suite was run. Reproduction commands and current artifact locations are documented in the repository README.
