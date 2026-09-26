# Prior art and contribution boundary

This repository contributes a focused empirical corpus: concrete expiry-consistency failures in two public agent-business simulators, pinned source evidence, passing controls, and diagnostic corrections checked against the same inputs. It does not claim a new inventory algorithm, a new testing paradigm, or the first expiry-related defect report.

## Established work

Lot tracking, cohort-preserving transfers, oldest-receipt-first consumption, FIFO/FEFO policies, and per-lot expiry checks are established inventory techniques. The [pinned Prosus engine](https://github.com/ProsusAI/vending-bench/blob/f9a1d7efde193de2242ed5afb1f3a326e362c75d/tasks/vending-bench/environment/sim-server/vending/engine.py) already stores warehouse receipt batches and expiry dates. Extending that information through machine slots is a conventional correction. Similarly, filtering Retail units with their existing expired predicate is conventional eligibility checking.

Metamorphic testing of simulations is established. M. S. Raunak and Megan Olsen's 2021 [Metamorphic Testing on the Continuum of Verification and Validation of Simulation Models](https://www.nist.gov/publications/metamorphic-testing-continuum-verification-and-validation-simulation-models) discusses its use for both verification and validation. [Gotten's cloud-simulator example](https://g0tten.github.io/evaluation.html) demonstrates a generic model-driven framework with domain-specific metamorphic relations. These precedents rule out claiming that a small oracle plus transformed simulator inputs is itself a new general method.

[Rahman and Izurieta's 2023 banking study](https://www.cs.montana.edu/izurieta/pubs/IRI_2023.pdf) derives metamorphic relations from banking function specifications and evaluates them with mutation analysis. Business-specific invariant testing is therefore also established; this corpus makes no general methodological improvement claim over that work.

[SolarChain-Eval](https://arxiv.org/html/2607.08681v1) already examines economic-agent reward against physical validity and demonstrates how invalid supply can improve reward. The idea of checking domain constraints before trusting economic reward is not new. The distinction here is the specific expiry findings in separately published implementations, with pinned reproductions and transferable case coverage, rather than a new general validity principle or an authored energy-market benchmark.

Agent vending-business evaluation also predates this work. [Andon Labs' Vending-Bench 2](https://andonlabs.com/evals/vending-bench-2) explicitly permits unbounded scores and gameable sales equations. A high reward or an economically unusual strategy therefore does not by itself establish a defect. This corpus asks a narrower question: does a supported state transition or ordinary sale remain consistent with the declared age contract and the simulator's own date convention?

## Competent baselines and demonstrated difference

| Baseline | What this repository adds or does not claim |
|---|---|
| Existing Prosus quantity/capacity tests | All 58 engine tests pass on the pinned original. The ten-case corpus exposes six related failures involving dated stock. This is evidence of missing age coverage, not evidence that the existing suite is generally weak. |
| Straightforward perishable unit regressions | The corpus adds real public-operation Prosus traces, paired controls, mixed cohorts, a second component-level implementation, and explicit observation phases. Individual assertions remain ordinary regression tests. |
| One earliest expiry for an entire slot | The mixed-age retention case requires fresh stock to remain after older stock expires. Whole-slot early removal fails that case. |
| Conventional complete lot tracking and expiry eligibility | These are the diagnostic corrections, not methods this project outperforms. The demonstrated advantage concerns verification coverage and reproducible evidence. |
| A general metamorphic-testing framework | Such frameworks can express relevant relations. This project supplies concrete fixtures, source observations, and domain-specific limits; it claims no general expressiveness or performance advantage. |

## Search boundary

The bounded prior-art review ran on 26–27 September 2026. It inspected the public source and tests of the pinned Prosus release, its publicly listed issues and pull requests, the anonymized RetailBench release's relevant inventory and date-handling code, and simulation/metamorphic-testing references. Searches included the simulator names with expiry, spoilage, `loaded_day`, perishable stock, and stock-age testing.

That review did not locate the same corpus or the specific findings reproduced here. It was nonexhaustive: it cannot establish worldwide novelty, exclude unpublished/private work, or guarantee that later releases remain affected. RetailBench's anonymous source lacks an immutable commit and does not support a claim that every author-side test or issue was searched. Findings are limited to the source bytes in the [manifests](../third_party/).

The defensible contribution is the new empirical evidence and its reviewable regression artifact. The patches and checker use established techniques. Upstream implementations retain their authorship, license, and credit as described in [NOTICE](../NOTICE.md).
