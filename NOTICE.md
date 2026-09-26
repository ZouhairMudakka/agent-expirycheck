# Authorship, attribution, and third-party notices

The newly authored `agent-expirycheck` checker, corpus, adapters, reproduction tooling, and documentation are Copyright (c) 2026 Zouhair Mudakka and are provided under the repository's [MIT License](LICENSE), except where a file identifies third-party material or an upstream-derived patch. This work was developed with AI assistance under Zouhair Mudakka's direction. Upstream code, benchmark design, and prior methods are not claimed as original work by this project.

## Prosus Vending Bench

**Prosus Vending Bench — Copyright 2026 MIH AI B.V.**

Selected files from [`ProsusAI/vending-bench`](https://github.com/ProsusAI/vending-bench/tree/f9a1d7efde193de2242ed5afb1f3a326e362c75d), commit `f9a1d7efde193de2242ed5afb1f3a326e362c75d`, are retained under the **Apache License, Version 2.0**. The complete upstream [LICENSE](third_party/prosus/LICENSE), [NOTICE](third_party/prosus/NOTICE), and [citation file](third_party/prosus/CITATION.cff) are preserved. The upstream NOTICE includes its Harbor attribution, benchmark-data request, and authorship statement; this summary does not replace it.

The [Prosus patch](patches/prosus.patch) is an authored diagnostic modification to that implementation: it retains receipt cohorts through slot transfers, sales, and expiry, and adds focused regression tests. The patch and resulting upstream-derived files remain under Apache-2.0, with the upstream notices retained. The repository's MIT license does not relicense those files. [Source](third_party/prosus-manifest.json) and [correction](patches/prosus-manifest.json) manifests distinguish original and modified bytes.

## RetailBench

**MIT License — Copyright (c) 2026 RetailBench Contributors**

Selected files from the publicly anonymized [RetailBench release `RetailBench_ARR-6253`](https://anonymous.4open.science/r/RetailBench_ARR-6253/README.md), retrieved 26–27 September 2026, retain the full upstream [MIT license and copyright notice](third_party/retail/LICENSE). This project preserves that attribution and does not attempt to identify the anonymous contributors. Selected downloaded bytes are pinned in the [source manifest](third_party/retail-manifest.json); no immutable upstream Git commit is asserted.

The [Retail patch](patches/retail.patch) changes ordinary-sale eligibility while retaining the implementation's native expiry predicate and cleanup phase. This diagnostic modification and its resulting upstream-derived file remain MIT-licensed with the RetailBench notice retained. New fixtures, hooks, and observations belong to this project and are not attributed to the RetailBench authors. The [correction manifest](patches/retail-manifest.json) records changed bytes.

## Prior methods and relationship to upstream

Lot accounting, expiry eligibility, and metamorphic testing are established techniques; see [prior-art notes](docs/prior-art.md). The contribution claimed here is the specific empirical corpus and reproducible observations. Inclusion and attribution do not imply upstream review, endorsement, acceptance of the contracts, or adoption of either diagnostic patch.
