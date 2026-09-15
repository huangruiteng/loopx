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


def test_bounded_producer_scan_rejects_unregistered_write() -> None:
    smoke = runpy.run_path(str(SMOKE))
    source = smoke["SourceFile"](
        "loopx/control_plane/quota/probe.py",
        ".py",
        'def produce():\n    return {"effective_action": "unregistered_action"}\n',
    )
    with pytest.raises(smoke["Drift"], match="unregistered_action"):
        smoke["check_producers"](
            {
                "vocabularies": {
                    "effective_action": {
                        "tier": "kernel",
                        "owners": {"python": None, "typescript": None},
                        "values": ["registered_action"],
                        "producers": ["loopx/control_plane/quota/probe.py::produce"],
                        "literal_scan": {"field": "effective_action", "roots": ["loopx"], "suffixes": [".py"]},
                    }
                }
            },
            [source],
        )


def test_bounded_producer_scan_does_not_treat_consumer_reads_as_writes() -> None:
    smoke = runpy.run_path(str(SMOKE))
    source = smoke["SourceFile"](
        "loopx/control_plane/quota/probe.py",
        ".py",
        'def consume(payload):\n    return payload.get("effective_action") == "registered_action"\n',
    )
    assert smoke["_producer_literals"]("effective_action", source) == set()


def test_bounded_context_scope_excludes_only_declared_multi_value_fork() -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = smoke["load_registry"]()
    sources = smoke["load_sources"](REPO_ROOT)
    inventory = smoke["build_inventory"](REPO_ROOT, sources=sources)
    assert smoke["check_scope_declarations"](registry, inventory) == 3


def test_bounded_context_scope_requires_every_distinct_defining_module() -> None:
    smoke = runpy.run_path(str(SMOKE))
    registry = copy.deepcopy(smoke["load_registry"]())
    registry["scope_declarations"]["SOURCE_SURFACES"]["contexts"] = registry["scope_declarations"]["SOURCE_SURFACES"]["contexts"][:-1]
    sources = smoke["load_sources"](REPO_ROOT)
    inventory = smoke["build_inventory"](REPO_ROOT, sources=sources)
    with pytest.raises(smoke["Drift"], match="every defining module"):
        smoke["check_scope_declarations"](registry, inventory)
