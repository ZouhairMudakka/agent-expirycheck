# Limits and interpretation

These 18 selected cases cover two related expiry-consistency defect families. They are not a full benchmark evaluation, a prevalence estimate, a model ranking, or an estimate of business profit or return on investment. No LLM policy, paid model call, or real business operation is part of the reproduction.

## What the checker can establish

The checker relies on declared original cohorts, native date rules, phases, and adapter measurements. Input hashes prevent accidental mismatching; they do not attest execution or detect fabricated measurements. New adapters must justify their own source facts and phase mapping. Reusing a passing observation with a dishonest description is outside this trust model.

Prosus exposes aggregate quantities in the public traces. A five-unit mixed-cohort result checks the right total, but cannot independently identify all five surviving units. The separate correction unit tests inspect cohort metadata; they are a different evidence level. Count-only sales likewise cannot identify sold cohorts with mixed eligibility, which that observation form refuses.

Retention cases require no sales. Unit-identified Retail cases additionally check lifecycle accounting, expiry removal, and declared sale-policy controls. None of these checks verifies demand realism, supplier behavior, price elasticity, refunds in general, or the entire simulator state. Passing the corpus is not a certification of a simulator or patch.

## Prosus scope and correction consequences

The Prosus cases invoke actual public business-tool methods in process and procure a supported perishable. They do not run the MCP transport, a containerized agent session, or a full simulation horizon. Branches consume their normal tool time; different action sequences need not have identical revenue opportunities or economics. Diagnostic reads avoid closing-time boundaries because a tool result can be built before its time charge rolls the day.

Age preservation is a stated consistency contract supported by the originally reported expiry and transfer language. The experiment does not prove that every physical food product must keep its expiry after every real-world treatment. It also does not prohibit an explicitly modeled preservation operation. The tested implementation has no such treatment explaining these transfers.

The diagnostic correction retains per-slot cohorts and their original received day, expiry, and unit cost. It consumes oldest received cohorts first, extending the existing warehouse rule; this is not a model of physical slot arrangement or a claim that FIFO is universally preferable to FEFO. Day-E sales still occur before day-E cleanup. Prices, catalogue, demand logic, tool durations, fees, and payment handling remain unchanged.

Retaining actual cohort costs has an accounting consequence: the original slot representation rounds a weighted average cost per unit, whereas the correction values the remaining cohorts. Net-worth cents and the remaining average can therefore differ. This is disclosed behavior, not broad economic equivalence.

A limited fallback supports manually authored upstream test slots without cohort metadata by treating their `loaded_day` and average cost as one cohort. It cannot recover historical receipt dates. Empty manual slots also clear stale cohort entries. This is **not a migration guarantee for old persisted runs**. Corrected-state serialization has a focused regression check, but no state-format migration, production rollout, performance study, or extensive malformed-state compatibility work is claimed.

## Retail scope and correction consequences

Retail evidence is component-level. The probe uses released inventory/product/sale/refund code with an authored SKU and cohorts, a passive review hook, and a recording writer instead of SQLite. Real NumPy demand sampling runs under explicit seeds. The real product archive, environment constructor, agent-facing `end_today`, and full public-tool procurement path are not exercised. Consecutive dates are passed directly to `Inventory.step`; wrapper date ordering was inspected statically.

Only canonical `power` demand mode is tested. The patch's shared eligibility view affects both sale branches, but this repository makes no validation claim for the other branch. No native Retail regression suite was run. The anonymous release is pinned by selected file hashes and should not be treated as a continuously maintained Git version.

The correction excludes units already expired under the native predicate from market membership, available-unit counts, and ordinary sale selection. It leaves physical inventory for the existing cleanup phase, preserves expiry-date equality, and does not change return handling or admit waiting stock earlier. The cleanup in these source bytes multiplies purchase price by zero, despite comments referring to a discounted amount. The finding concerns the distinct ordinary-sale path, not a prohibition on separate liquidation channels.

All five controls retain inventory, monetary, and lifecycle outcomes. Four retain the complete observation record. In `expired-zero-demand-cleanup`, `sales_by_sku` changes from `{"AUTHORED-COHORT": 0}` to `{}` because an expired-only SKU no longer enters the market list. This exact representation difference is disclosed. In larger multi-SKU runs, changing market membership may also change demand allocation and random-number consumption. Distributional equivalence is untested.

## What would require further evidence

Effects on long-horizon agent decisions, published scores, rankings, profitability, and real retail outcomes require separate studies. Broad patch readiness would require upstream review, integration coverage, and compatibility decisions. The observations here are evidence about the pinned implementations under the declared contracts, not a declaration that either benchmark is invalid.
