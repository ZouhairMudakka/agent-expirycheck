# Retained evidence

`reference/` contains one completed local Python 3.12.14 Windows reproduction, including the 18-case observations, independently derived reports, raw public-tool/component evidence, source/patch/adapter digests, and native test logs. The original has 9 passes and 9 measured failures; the diagnostic corrections have 18 passes. No adapter errors occurred.

These are retained observations, not expected-answer tables for the checker. The runner recreates all inputs and measures the source again. `summary.json` records one machine's elapsed runtime, including subprocess startup and native tests; it is not a performance benchmark. Dependency installation time is excluded. The workflow reruns on Linux and Windows.

```sh
expirycheck results/reference/original.json --corpus corpus/cases.json
# exit 1, the observed violations
expirycheck results/reference/corrected.json --corpus corpus/cases.json
# exit 0
```

Provenance hashes cover source manifests, correction manifests, patches, adapters, and corpus. Native Prosus tests are unmodified and run in separate source copies; the corrected test log also includes nine authored diagnostic tests. Retail has no native-suite result here. Raw Prosus traces contain fictional supplier/company names and simulated business state from the public benchmark. No real transactions or credentials are involved.
