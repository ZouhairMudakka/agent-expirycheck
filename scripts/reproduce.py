"""Run both pinned originals and diagnostic corrections. No network/model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
# This runner reproduces a particular release. The reusable CLI accepts any
# separately declared corpus, but changing release inputs must not retain the
# label 'matches_published_results'.
PUBLISHED_CORPUS_SHA256 = "8f283e30d85fcdadc8d0767a4df2bcaa1005bc23c25667831908f5f224723e02"
sys.path.insert(0, str(ROOT / "src"))
from expirycheck import evaluate  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_tree(tree: Path, manifest: dict) -> None:
    actual_paths = {path.relative_to(tree).as_posix() for path in tree.rglob("*") if path.is_file()}
    expected_paths = {entry["path"] for entry in manifest["files"]}
    if actual_paths != expected_paths:
        raise RuntimeError(f"Source coverage mismatch in {tree}: missing={expected_paths - actual_paths}, extra={actual_paths - expected_paths}")
    for entry in manifest["files"]:
        path = tree / entry["path"]
        if digest(path) != entry["sha256"]:
            raise RuntimeError(f"Pinned source mismatch: {path}")


def run(command: list[str], *, cwd: Path, env: dict, log: Path) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, encoding="utf-8",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout, encoding="utf-8", newline="\n")
    if result.returncode:
        raise RuntimeError(f"Subprocess failed ({result.returncode}); see {log}\n{result.stdout[-3000:]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--skip-upstream-tests", action="store_true",
                        help="Only reproduce the 18 cases; do not claim native test coverage")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT.is_relative_to(output):
        parser.error("Output must be a dedicated directory, not the repository or its parent")
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").unlink(missing_ok=True)
    corpus = (ROOT / "corpus/cases.json").read_bytes()
    if hashlib.sha256(corpus).hexdigest() != PUBLISHED_CORPUS_SHA256:
        raise RuntimeError("Corpus differs from the published 18-case release; use the checker CLI for a custom corpus")
    env = os.environ.copy()
    # Native benchmark configuration accepts env overrides. Do not let a host's
    # unrelated experiment silently change the pinned fixture.
    for key in list(env):
        if key.startswith("VENDING_"):
            del env[key]
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT / "src"), MPLCONFIGDIR=str(output / ".matplotlib"))
    start = time.perf_counter()
    reports = {}
    provenance = {}
    expected_failures = {
        "prosus/aged_load", "prosus/clear_to_depot", "prosus/top_up_same_cohort",
        "prosus/sale_after_reported_expiry", "prosus/mixed_old_expires_fresh_survives",
        "prosus/mixed_all_expire", "retail/after-expiry", "retail/unshelved-then-shelved",
        "retail/mixed-expiry-cohorts",
    }
    all_observations = {"original": [], "corrected": []}
    # Temporary copies leave the vendored originals immutable. Git only applies
    # local reviewed patches; it never fetches anything here.
    with tempfile.TemporaryDirectory(prefix="agent-expirycheck-") as temp:
        for target in ("prosus", "retail"):
            manifest_path = ROOT / "third_party" / (target + "-manifest.json")
            manifest = json.loads(manifest_path.read_bytes())
            original = ROOT / "third_party" / target
            verify_tree(original, manifest)
            correction_path = ROOT / "patches" / (target + "-manifest.json")
            correction = json.loads(correction_path.read_bytes())
            patch = ROOT / "patches" / (target + ".patch")
            if digest(patch) != correction["patch_sha256"]:
                raise RuntimeError(f"Patch hash mismatch: {target}")
            provenance[target] = {
                "source_manifest_sha256": digest(manifest_path),
                "correction_manifest_sha256": digest(correction_path),
                "patch_sha256": digest(patch),
                "adapter_sha256": digest(ROOT / "adapters" / (target + ".py")),
            }
            for variant in ("original", "corrected"):
                tree = Path(temp) / (target + "-" + variant)
                shutil.copytree(original, tree)
                if variant == "corrected":
                    run(["git", "-c", "core.autocrlf=false", "apply", "--no-index", str(patch)], cwd=tree, env=env,
                        log=output / (target + "-patch.log"))
                    for change in correction["files"]:
                        if digest(tree / change["path"]) != change["corrected_sha256"]:
                            raise RuntimeError(f"Corrected bytes differ: {change['path']}")
                    corrected_hashes = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
                    corrected_hashes.update({entry["path"]: entry["corrected_sha256"] for entry in correction["files"]})
                    verify_tree(tree, {"files": [{"path": path, "sha256": sha} for path, sha in corrected_hashes.items()]})
                raw = output / f"{target}-{variant}.json"
                run([sys.executable, str(ROOT / "adapters" / (target + ".py")),
                     "--source-tree", str(tree), "--output", str(raw),
                     "--corpus", str(ROOT / "corpus/cases.json")], cwd=tree, env=env,
                    log=output / f"{target}-{variant}.log")
                all_observations[variant].extend(json.loads(raw.read_bytes())["observations"])
                if target == "prosus" and not args.skip_upstream_tests:
                    tests = ["tests/test_engine.py"]
                    if variant == "corrected":
                        tests.append("tests/test_stock_age_diagnostic.py")
                    run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
                        cwd=tree, env=env, log=output / f"prosus-{variant}-tests.log")
            verify_tree(original, manifest)
    for variant, observations in all_observations.items():
        envelope = {
            "schema_version": 1,
            "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
            "adapter": "prosus+retail/" + variant,
            "observations": observations,
            "metadata": {"source": provenance},
        }
        (output / (variant + ".json")).write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8", newline="\n")
        report = evaluate(corpus, envelope)
        reports[variant] = report
        (output / (variant + "-report.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    # This is a reproduction assertion, not the independent oracle. The oracle
    # derives violations from the frozen cohorts/rules, never from this list.
    observed_failures = {row["case_id"] for row in reports["original"]["cases"] if row["status"] == "fail"}
    if observed_failures != expected_failures or reports["original"]["errors"]:
        raise RuntimeError("Original observations do not reproduce the published failure set")
    if reports["corrected"]["failed"] or reports["corrected"]["errors"]:
        raise RuntimeError("Diagnostic corrections violate the frozen contract")
    summary = {
        "reproduction": "matches_published_results",
        "original": {key: reports["original"][key] for key in ("checked", "passed", "failed", "errors")},
        "corrected": {key: reports["corrected"][key] for key in ("checked", "passed", "failed", "errors")},
        "upstream_tests_run": not args.skip_upstream_tests,
        "runtime_seconds": round(time.perf_counter() - start, 3),
        "python": sys.version,
        "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
        "provenance": provenance,
        "scope": "Targeted deterministic cases, two root-cause families; no LLM/full-agent evaluation",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
