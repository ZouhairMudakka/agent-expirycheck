# agent-expirycheck

**Check that a business simulator preserves stock expiry before trusting an agent's results.**

An 18-case corpus, a small independent checker, and reproducible findings in two public agent-business simulators. Under the corpus's stated age-preservation contract, moving unchanged stock must not renew its declared age; ordinary sales must respect the simulator's own expiry boundary. The checks also require fresh stock to survive or sell, so discarding everything does not pass.

| Pinned implementation | Original | Diagnostic correction | Observed failure family |
|---|---:|---:|---|
| [Prosus Vending Bench](https://github.com/ProsusAI/vending-bench/tree/f9a1d7efde193de2242ed5afb1f3a326e362c75d) | 4/10 pass | 10/10 pass | Receipt age is lost across transfers and top-ups |
| [RetailBench anonymous source](https://anonymous.4open.science/r/RetailBench_ARR-6253/README.md) | 5/8 pass | 8/8 pass | Already-expired units enter ordinary sales before cleanup |

These are **two root-cause families**, not nine independent bugs or a defect-rate estimate. Prosus is exercised through actual in-process public tool methods, from real simulated paid orders. RetailBench uses its real inventory component with an authored product and passive review/database hooks. Neither is a full LLM evaluation.

The unchanged Prosus implementation passes all **58 existing engine tests**, including its reference-operator checks. The expiry corpus exposes behavior those tests do not cover. The correction also passes those 58 tests plus nine focused diagnostic tests.

## Reproduce

Use Python **3.12** and Git. The selected upstream files are included with their original licenses and exact hashes. After dependency installation, reproduction needs no network, credentials, model, or paid API.

```sh
python -m venv .venv
# Activate: source .venv/bin/activate (POSIX)
# Or: .venv\Scripts\Activate.ps1 (PowerShell)
python -m pip install -r requirements-reproduce.txt
python -m pip install --no-deps -e .
python -m pytest -q
python scripts/reproduce.py
```

The runner verifies source hashes, applies the reviewed patches only to temporary copies, observes both versions in separate processes, runs the native Prosus tests, and writes traces, observations, reports, and provenance to `artifacts/`. Successful reproduction means **original 9/18 pass and corrected 18/18 pass**, with the exact published failure set. It does not mean the originals satisfy the contract.

[Retained reference observations and reports](results/reference/) are included for inspection without installing the reproduction dependencies. They are also accepted by the standard-library checker.

```sh
expirycheck artifacts/original.json --corpus corpus/cases.json
# exit 1: measured violations, deliberately reproduced
expirycheck artifacts/corrected.json --corpus corpus/cases.json
# exit 0: all declared checks pass
```

Checker exit codes: **0** all pass; **1** measured violation; **2** invalid/missing evidence or adapter error. The checker itself uses only Python's standard library. Reproduction dependencies are needed for the upstream RetailBench component and pytest, not for checking saved observations.

## What the contribution is

The contribution is the **specific reproducible evidence and reusable coverage**: an explicit phase-aware contract, source-cohort facts separated from observed outcomes, mixed-age and fresh-sale controls, two target adapters, and diagnostic corrections against pinned originals. The checker derives expected eligibility from the corpus; adapters do not supply expected answers. Corpus and case hashes prevent accidentally pairing observations with different input facts. They do not authenticate an untrusted adapter.

FIFO/lot tracking, expiry filtering, and metamorphic testing are established. The patches are conventional ways to diagnose the findings. We did not locate these exact findings or an equivalent corpus in the bounded public-work review; that is not proof of universal novelty. See [prior art](docs/prior-art.md), [methods and case coverage](docs/methods.md), and [limits](docs/limits.md).

One concrete witness: a Prosus batch publicly reported to expire on day 16 can sell two units on day 17 after transfer, producing **EUR 8.40 of synthetic gross revenue**. The correction prevents that sale. This is a simulator observation, not profit, real money, measured production savings, or evidence that a model ranking changes.

## Use the checker with your simulator

Write a small adapter that observes original cohort expiry, the native comparison/phase, and either unsold remaining quantities or unit-level sale/removal identities. Supply every case declared in your own corpus and bind each row with `case_digest(case)` and the envelope with SHA-256 of the raw corpus bytes. Run `expirycheck observations.json --corpus your-cases.json`.

The three supported checks are deliberately narrow:

- `retention`: after expiry cleanup, unsold original cohorts leave the expected aggregate quantity. Any sale makes this check inapplicable.
- `sales`: each unit appears exactly once in ordinary sales, expired removal, or remaining stock. Expired ordinary sales and fresh expiry removal fail; declared sale/cleanup policies constrain empty-output shortcuts.
- `sale_count`: an eligibility bound for a homogeneous cohort when unit identities are unavailable. It does not verify cleanup or demand.

[The adapter contract](docs/adapter-contract.md) gives a complete minimal example. The supplied adapters cover only the documented fixtures. The tool does not infer inventory capabilities or validate an entire economy.

## Practical value and limits

This is intended as an inexpensive simulator regression check before spending on long agent runs. It can reveal cases where a policy benefits from stock-age loss or invalid ordinary sales. Actual savings, customer demand, willingness to pay, and commercial viability have not been measured. It is presently a focused open-source research/developer tool.

The diagnostic patches are not production-ready upgrades. Prosus's cohort valuation can differ from its old rounded average; historical state migration is not established. RetailBench is tested only in the documented `power` mode, with a limited hook fixture, and one zero-demand summary changes from a zero-valued SKU entry to an empty map. See [all limits](docs/limits.md).

## Attribution

Authored by **Zouhair Mudakka**, with AI-assisted research and implementation. New checker, adapters, corpus, and documentation: [MIT](LICENSE). Vendored Prosus files and its derivative patch retain **Apache-2.0**; RetailBench files and its derivative patch retain **MIT** and the anonymous contributors' attribution. Upstream authors do not endorse these findings or corrections. See [NOTICE](NOTICE.md) and the preserved licenses under `third_party/`.
