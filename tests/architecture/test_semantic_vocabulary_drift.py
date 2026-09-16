"""Run the semantic vocabulary drift smoke inside the pull-request pytest sweep.

The canary fleet discovers ``examples/**/*-smoke.py`` on its own, but the fleet
runs after merge and on a schedule, and ``loopx canary premerge`` selects smokes
by changed-path tokens. Neither is a commit-time check for a diff that only
touches ``loopx/``. This wrapper is the PR-path obligation named in the RFC
``docs/architecture/rfcs/semantic-vocabulary-convergence-v0.md`` (Section 10):
the smoke fails closed here on every pull request that runs the Python tests.
"""

from __future__ import annotations

import copy
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "examples" / "semantic-vocabulary-drift-smoke.py"


def test_semantic_vocabulary_registry_matches_the_code() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", str(SMOKE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, (
        "semantic vocabulary drift smoke failed; the registry, the inventory, or an "
        "anchor no longer matches the code:\n" + completed.stdout + completed.stderr
    )
    assert completed.stdout.startswith("semantic-vocabulary-drift-smoke: ok"), (
        completed.stdout
    )


@pytest.mark.parametrize("mutation", ["twin_budget", "twin_root", "scan_root"])
def test_registry_cannot_relax_scan_scope_or_twin_budget(mutation: str) -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke["load_registry"]())
    if mutation == "twin_budget":
        registry["dual_runtime_twins"]["module_budget"] += 1
    elif mutation == "twin_root":
        registry["dual_runtime_twins"]["root"] = "loopx/semantics"
    else:
        registry["vocabularies"]["effective_action"]["literal_scan"]["roots"] = ["loopx/control_plane"]
    with pytest.raises(smoke["Drift"]):
        smoke["check_coverage_floor"](registry)
        smoke["check_dual_runtime_twins"](registry)


@pytest.mark.parametrize("suffix", [".py", ".ts"])
@pytest.mark.parametrize("quote", ["'", '\"'])
def test_literal_scan_rejects_unknown_value_with_either_quote(suffix: str, quote: str) -> None:
    smoke = runpy.run_path(str(SMOKE))
    text = f"effective_action = {quote}unregistered_action{quote}"
    sources = [smoke["SourceFile"]("loopx/probe" + suffix, suffix, text)]
    with pytest.raises(smoke["Drift"], match="unregistered_action"):
        smoke["check_literal_vocabularies"](smoke["load_registry"](), sources)


def test_candidate_decisions_are_exhaustive_and_default_to_unknown() -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = smoke["load_registry"]()
    candidate_decisions = registry["formal_model"]["candidate_decisions"]
    assert candidate_decisions["default"] == "unknown"
    assert set(candidate_decisions["values"]) == {
        "reuse_existing",
        "extend_vocabulary",
        "create_vocabulary",
        "local_only",
        "external_input",
        "compatibility_only",
        "unknown",
    }

    registry["formal_model"]["candidate_decisions"]["default"] = "reuse_existing"
    with pytest.raises(smoke["Drift"], match="default unresolved candidates"):
        smoke["check_formal_model"](registry["formal_model"])
