"""Regression checks for evidence binding and reproduction provenance.

These tests never run the full 18-case reproduction. The Prosus subprocesses
stop at a changed-input guard; patch tests simulate the patch output locally.
"""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("expirycheck_reproduce_test", ROOT / "scripts/reproduce.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return sha256(content).hexdigest()


def configure_runner(runner, monkeypatch, root, output):
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(sys, "argv", ["reproduce.py", "--output", str(output), "--skip-upstream-tests"])


@pytest.mark.parametrize("change", ["remove-passing-control", "alter-expiry"])
def test_changed_release_corpus_rejected_and_stale_success_removed(runner, monkeypatch, tmp_path, change):
    corpus = json.loads((ROOT / "corpus/cases.json").read_bytes())
    if change == "remove-passing-control":
        corpus["cases"] = [case for case in corpus["cases"] if case["case_id"] != "retail/before-expiry"]
    else:
        corpus["cases"][0]["cohorts"][0]["expiry"] += 1
    root, output = tmp_path / "release", tmp_path / "results"
    write(root / "corpus/cases.json", json.dumps(corpus).encode())
    write(output / "summary.json", b'{"reproduction":"matches_published_results"}\n')
    configure_runner(runner, monkeypatch, root, output)

    def unexpected_run(*args, **kwargs):
        pytest.fail("A changed release must be rejected before executing an adapter or patch")

    monkeypatch.setattr(runner, "run", unexpected_run)
    with pytest.raises(RuntimeError, match="Corpus differs from the published 18-case release"):
        runner.main()
    assert not (output / "summary.json").exists()


@pytest.mark.parametrize("extra", ["tests/conftest.py", "module/__init__.py"])
def test_source_manifest_rejects_unmanifested_executable_files(runner, tmp_path, extra):
    expected_hash = write(tmp_path / "module/inventory.py", b"# pinned source\n")
    manifest = {"files": [{"path": "module/inventory.py", "sha256": expected_hash}]}
    runner.verify_tree(tmp_path, manifest)
    write(tmp_path / extra, b"# additional executable input\n")
    with pytest.raises(RuntimeError, match="Source coverage mismatch"):
        runner.verify_tree(tmp_path, manifest)


@pytest.mark.parametrize("damage", ["untouched-source", "additional-file"])
def test_corrected_tree_is_fully_verified_before_adapter_execution(runner, monkeypatch, tmp_path, damage):
    root, output = tmp_path / "release", tmp_path / "results"
    write(root / "corpus/cases.json", (ROOT / "corpus/cases.json").read_bytes())
    tree = root / "third_party/prosus"
    engine_hash = write(tree / "engine.py", b"# original engine\n")
    helper_hash = write(tree / "helper.py", b"# unchanged helper\n")
    manifest = {"files": [{"path": "engine.py", "sha256": engine_hash},
                           {"path": "helper.py", "sha256": helper_hash}]}
    write(root / "third_party/prosus-manifest.json", json.dumps(manifest).encode())
    patch_hash = write(root / "patches/prosus.patch", b"# authored fake patch input\n")
    corrected_engine, added_test = b"# corrected engine\n", b"# added diagnostic test\n"
    correction = {"patch_sha256": patch_hash, "files": [
        {"path": "engine.py", "original_sha256": engine_hash, "corrected_sha256": sha256(corrected_engine).hexdigest()},
        {"path": "tests/test_diagnostic.py", "original_sha256": None, "corrected_sha256": sha256(added_test).hexdigest()},
    ]}
    write(root / "patches/prosus-manifest.json", json.dumps(correction).encode())
    write(root / "adapters/prosus.py", b"# subprocess is replaced for this provenance test\n")
    configure_runner(runner, monkeypatch, root, output)
    adapter_runs = []

    def fake_run(command, *, cwd, env, log):
        if command[0] == "git":
            # All declared corrected hashes are right. The extra change must
            # still be caught by the complete corrected-tree verification.
            write(cwd / "engine.py", corrected_engine)
            write(cwd / "tests/test_diagnostic.py", added_test)
            if damage == "untouched-source":
                write(cwd / "helper.py", b"# accidentally changed helper\n")
            else:
                write(cwd / "tests/conftest.py", b"# unexpected test hook\n")
        else:
            adapter_runs.append(cwd.name)
            assert cwd.name == "prosus-original", "Corrected adapter ran before complete source verification"
            raw = Path(command[command.index("--output") + 1])
            write(raw, b'{"observations":[]}\n')

    monkeypatch.setattr(runner, "run", fake_run)
    expected_message = "Pinned source mismatch" if damage == "untouched-source" else "Source coverage mismatch"
    with pytest.raises(RuntimeError, match=expected_message):
        runner.main()
    assert adapter_runs == ["prosus-original"]
    assert not (output / "summary.json").exists()


@pytest.mark.parametrize("change", ["quantity-and-expiry", "checked-day", "comparison", "kind"])
def test_prosus_rejects_corpus_facts_that_do_not_describe_its_trace(tmp_path, change):
    corpus = json.loads((ROOT / "corpus/cases.json").read_bytes())
    case = next(case for case in corpus["cases"] if case["case_id"] == "prosus/aged_load")
    if change == "quantity-and-expiry":
        # The original retains eight units. Relabelling the source cohort as
        # eight unexpired units previously turned this real failure into a pass.
        case["cohorts"][0].update(quantity=8, expiry=99)
    elif change == "checked-day":
        case["day"] = 14
    elif change == "comparison":
        case["expiry_rule"]["comparison"] = "lt"
    else:
        case["kind"] = "sale_count"
        case["expiry_rule"] = {"phase": "before_sales", "comparison": "lt"}
    corpus_path, output = tmp_path / "changed.json", tmp_path / "observations.json"
    write(corpus_path, json.dumps(corpus).encode())
    env = {key: value for key, value in os.environ.items() if not key.startswith("VENDING_")}
    env.update(PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    result = subprocess.run(
        [sys.executable, str(ROOT / "adapters/prosus.py"), "--source-tree", str(ROOT / "third_party/prosus"),
         "--corpus", str(corpus_path), "--output", str(output)],
        cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode != 0
    assert "Public-tool fixture does not implement declared facts: prosus/aged_load" in result.stderr
    assert not output.exists()
