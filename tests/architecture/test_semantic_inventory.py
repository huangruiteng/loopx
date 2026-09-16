"""Semantics of the repository-wide vocabulary inventory scanner.

The inventory is the map behind the semantic vocabulary registry. These tests
pin the classification rules from the RFC rather than from scanner output:
which carriers count as closed sets, how duplicate constants split into
cross-runtime twins, same-runtime forks, and conflicting values, and that the
inventory is computed from the whole tracked tree without a committed snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from loopx.semantics.inventory import (
    INVENTORY_SCHEMA_VERSION,
    SourceFile,
    build_inventory,
    load_sources,
    python_facts,
    render_inventory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _write(
        tmp_path,
        "loopx/a.py",
        'from enum import Enum\n'
        'from typing import Literal\n'
        'class Kind(str, Enum):\n    ONE = "one"\n    TWO = "two"\n    _private = "ignored"\n'
        'class Mixed(Enum):\n    A = "a"\n    B = 2\n'
        'STATES = frozenset({"open", "closed"})\n'
        'SINGLE = ("only",)\n'
        'NOT_STRINGS = (1, 2)\n'
        'Mode = Literal["fast", "slow"]\n'
        'FOO_SCHEMA_VERSION = "foo_v0"\n'
        'SHARED = "same"\n'
        'CLASHING = "left"\n',
    )
    _write(
        tmp_path,
        "loopx/b.py",
        'SHARED = "same"\n'
        'CLASHING = "right"\n'
        'FOO_SCHEMA_VERSION = "foo_v0"\n'
        'PAIRED_SCHEMA_VERSION = "paired_v0"\n',
    )
    _write(
        tmp_path,
        "loopx/b.ts",
        'export const KINDS = ["one", "two"] as const;\n'
        'export const PAIRED_SCHEMA_VERSION = "paired_v0";\n'
        'export const NOT_CLOSED = ["x"];\n',
    )
    _write(tmp_path, "loopx/__pycache__/junk.py", 'IGNORED = ("a", "b")\n')
    _write(tmp_path, "loopx/node_modules/dep.ts", 'export const IGNORED = ["a", "b"] as const;\n')
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "loopx/a.py", "loopx/b.py", "loopx/b.ts"],
        check=True,
    )
    return tmp_path


def test_python_carriers_are_classified_by_shape(repo: Path) -> None:
    inventory = build_inventory(repo)
    enums = {entry["name"]: entry["values"] for entry in inventory["python_enums"]}
    assert enums == {"Kind": ["one", "two"]}, "only string-valued members of string enums are vocabularies"
    closed = {entry["name"]: entry for entry in inventory["python_closed_sets"]}
    assert set(closed) == {"STATES"}, "a closed set needs two or more string members"
    assert closed["STATES"]["container"] == "frozenset"
    assert [entry["values"] for entry in inventory["python_literal_aliases"]] == [["fast", "slow"]]


def test_typescript_as_const_arrays_only(repo: Path) -> None:
    inventory = build_inventory(repo)
    assert [entry["name"] for entry in inventory["typescript_const_arrays"]] == ["KINDS"]


def test_duplicate_constants_split_into_twin_fork_conflict(repo: Path) -> None:
    inventory = build_inventory(repo)["duplicate_definitions"]
    assert [entry["name"] for entry in inventory["cross_runtime_twins"]] == ["PAIRED_SCHEMA_VERSION"]
    assert [entry["name"] for entry in inventory["same_runtime_forks"]] == ["FOO_SCHEMA_VERSION", "SHARED"]
    assert [entry["name"] for entry in inventory["conflicting_values"]] == ["CLASHING"]
    fork = inventory["same_runtime_forks"][0]
    assert fork["is_schema_version"] is True
    assert fork["modules"] == ["loopx/a.py", "loopx/b.py"]


def test_summary_counts_and_skipped_directories(repo: Path) -> None:
    summary = build_inventory(repo)["summary"]
    assert summary["source_files"] == 3, "__pycache__ and node_modules are never scanned"
    assert summary["schema_version_names"] == 2
    assert summary["schema_version_same_runtime_forks"] == 1
    assert summary["cross_runtime_twins"] == 1
    assert summary["same_runtime_forks"] == 2
    assert summary["conflicting_values"] == 1


@pytest.fixture
def collision_repo(tmp_path: Path) -> Path:
    """A tree where multi-value carriers collide and local names look like drift.

    ``STATES`` is a closed set under two divergent value sets, ``TWIN_SET`` is one
    closed set written twice, and ``SCHEMA_VERSION`` / ``FOO_SCHEMA_VERSION`` are
    per-module names that must not be counted as shared vocabulary.
    """
    _write(
        tmp_path,
        "loopx/a.py",
        'STATES = frozenset({"open", "closed"})\n'
        'TWIN_SET = ("p", "q")\n'
        'SCHEMA_VERSION = "a_v1"\n'
        'FOO_SCHEMA_VERSION = "foo_v0"\n'
        'SHARED = "same"\n',
    )
    _write(
        tmp_path,
        "loopx/b.py",
        'STATES = frozenset({"open", "shut"})\n'
        'TWIN_SET = ("p", "q")\n'
        'SCHEMA_VERSION = "b_v1"\n'
        'FOO_SCHEMA_VERSION = "foo_v0"\n'
        'SHARED = "same"\n',
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "loopx/a.py", "loopx/b.py"], check=True,
    )
    return tmp_path


def test_multi_value_carriers_collide_like_string_constants(collision_repo: Path) -> None:
    """An enum or closed set carries vocabulary, so a duplicate name is drift.

    Before this rule the scanner listed multi-value carriers but never compared
    them, so a closed set defined in two modules with divergent values was
    invisible to every budget.
    """
    duplicates = build_inventory(collision_repo)["duplicate_definitions"]
    assert [entry["name"] for entry in duplicates["multi_value_forks"]] == ["STATES"]
    assert [entry["name"] for entry in duplicates["multi_value_twins"]] == ["TWIN_SET"]
    fork = duplicates["multi_value_forks"][0]
    assert [item["values"] for item in fork["definitions"]] == [
        ["open", "closed"],
        ["open", "shut"],
    ], "the fork keeps both value sets so a reviewer sees the divergence"
    assert [item["kind"] for item in fork["definitions"]] == [
        "python_closed_set",
        "python_closed_set",
    ]


def test_module_local_convention_names_stay_out_of_semantic_budgets(collision_repo: Path) -> None:
    """``SCHEMA_VERSION`` and ``FOO_SCHEMA_VERSION`` are per-module names, not drift.

    Counting them as conflicts measured local naming; the unfiltered totals stay
    visible, while only the shared-vocabulary subset is budgeted.
    """
    summary = build_inventory(collision_repo)["summary"]
    assert summary["conflicting_values"] == 1, "SCHEMA_VERSION still counts in the raw total"
    assert summary["conflicting_values_semantic"] == 0, "neither name is shared vocabulary"
    assert summary["same_runtime_forks"] == 2
    assert summary["same_runtime_forks_semantic"] == 1, "only SHARED is shared vocabulary"
    assert summary["multi_value_forks"] == 1
    assert summary["multi_value_twins"] == 1


def test_render_is_deterministic_valid_json(repo: Path) -> None:
    inventory = build_inventory(repo)
    rendered = render_inventory(inventory)
    assert rendered == render_inventory(build_inventory(repo))
    assert json.loads(rendered) == inventory
    assert inventory["schema_version"] == INVENTORY_SCHEMA_VERSION
    # one entry per line keeps diffs reviewable
    assert '    {"name": "Kind", "module": "loopx/a.py", "values": ["one", "two"]}' in rendered


def test_inventory_cli_defaults_to_json_without_writing(repo: Path, monkeypatch, capsys) -> None:
    from scripts import generate_semantic_inventory as generator

    legacy = repo / "loopx/semantics/inventory_v0.json"
    _write(repo, "loopx/semantics/inventory_v0.json", "obsolete report, not JSON")
    monkeypatch.setattr(generator, "ROOT", repo)
    monkeypatch.setattr(sys, "argv", ["generate_semantic_inventory"])
    assert generator.main() == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["schema_version"] == INVENTORY_SCHEMA_VERSION
    assert emitted["summary"]["source_files"] == 3
    assert legacy.read_text() == "obsolete report, not JSON"


def test_optional_inventory_report_check_never_repairs(repo: Path, monkeypatch, capsys) -> None:
    from scripts import generate_semantic_inventory as generator

    output = repo / ".local/reports/inventory.json"
    monkeypatch.setattr(generator, "ROOT", repo)
    args = ["generate_semantic_inventory", "--output", str(output)]
    monkeypatch.setattr(sys, "argv", args + ["--check"])
    assert generator.main() == 1
    assert not output.exists()
    monkeypatch.setattr(sys, "argv", args)
    assert generator.main() == 0
    saved = output.read_bytes()
    monkeypatch.setattr(sys, "argv", args + ["--check"])
    assert generator.main() == 0
    with (repo / "loopx/a.py").open("a") as stream:
        stream.write('ADDED = ("new", "carrier")\n')
    assert generator.main() == 1
    assert output.read_bytes() == saved
    assert "stale or missing" in capsys.readouterr().err


def test_snapshot_check_requires_an_explicit_report(monkeypatch, capsys) -> None:
    from scripts import generate_semantic_inventory as generator

    monkeypatch.setattr(sys, "argv", ["generate_semantic_inventory", "--check"])
    with pytest.raises(SystemExit) as exc:
        generator.main()
    assert exc.value.code == 2
    assert "--check requires --output" in capsys.readouterr().err


def test_full_tree_scan_detects_a_collision_with_an_unchanged_file(repo: Path) -> None:
    _write(repo, "loopx/old.py", 'Q9_SHARED = "existing"\n')
    subprocess.run(["git", "-C", str(repo), "add", "loopx/old.py"], check=True)
    assert not any(row["name"] == "Q9_SHARED" for row in build_inventory(repo)["duplicate_definitions"]["same_runtime_forks"])
    _write(repo, "loopx/new.py", 'Q9_SHARED = "existing"\n')
    subprocess.run(["git", "-C", str(repo), "add", "loopx/new.py"], check=True)
    fork = next(row for row in build_inventory(repo)["duplicate_definitions"]["same_runtime_forks"] if row["name"] == "Q9_SHARED")
    assert set(fork["modules"]) == {"loopx/old.py", "loopx/new.py"}


def test_untracked_sources_do_not_change_inventory(repo: Path) -> None:
    before = render_inventory(build_inventory(repo))
    _write(repo, "loopx/local_notes.py", 'PRIVATE_CONTEXT = ("synthetic", "local")\n')
    assert render_inventory(build_inventory(repo)) == before


def test_tracked_symlink_cannot_read_untracked_source(repo: Path) -> None:
    _write(repo, "private.py", 'PRIVATE_CONTEXT = ("synthetic", "local")\n')
    (repo / "loopx/link.py").symlink_to(repo / "private.py")
    subprocess.run(["git", "-C", str(repo), "add", "loopx/link.py"], check=True)
    with pytest.raises(ValueError, match="symlink"):
        load_sources(repo)


def test_invalid_python_source_is_not_reported_as_empty() -> None:
    with pytest.raises(ValueError, match="loopx/broken.py"):
        python_facts(SourceFile("loopx/broken.py", ".py", 'STATES = ("open",\n'))


def test_typescript_single_quoted_carriers_are_visible(repo: Path) -> None:
    _write(repo, "loopx/b.ts", "export const KINDS = ['one', 'two'] as const;\nexport const SHARED = 'same';\n")
    inventory = build_inventory(repo)
    assert inventory["typescript_const_arrays"][0]["values"] == ["one", "two"]
    assert any(item["name"] == "SHARED" for item in inventory["duplicate_definitions"]["same_runtime_forks"])
