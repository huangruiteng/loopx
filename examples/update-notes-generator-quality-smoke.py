#!/usr/bin/env python3
"""Validate deterministic, compact update-note source-draft generation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "update_notes_release_job.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("update_notes_release_job", GENERATOR)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load update-note generator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_merged_pr_collection(module) -> None:
    calls: list[list[str]] = []

    def fake_run_git(args: list[str]) -> str:
        calls.append(args)
        fs = module.FIELD_SEPARATOR
        rs = module.RECORD_SEPARATOR
        return rs.join(
            [
                fs.join(["aaa1111", "feat: ship useful capability (#42)", ""]),
                fs.join(
                    [
                        "bbb2222",
                        "Merge pull request #41 from example/topic",
                        "Fix quota boundary\n\nMore detail.",
                    ]
                ),
                fs.join(["ccc3333", "Merge branch 'main' into example/topic", ""]),
                fs.join(["ddd4444", "direct maintenance commit", ""]),
            ]
        )

    original = module.run_git
    module.run_git = fake_run_git
    try:
        commits = module.collect_commits(
            module.Window(module.parse_date("2026-07-01"), module.parse_date("2026-07-14"))
        )
    finally:
        module.run_git = original

    assert calls and "--first-parent" in calls[0], calls
    assert "--since=2026-07-01T00:00:00Z" in calls[0], calls
    assert "--until=2026-07-14T23:59:59Z" in calls[0], calls
    assert [(item.pr_number, item.subject) for item in commits] == [
        (42, "feat: ship useful capability"),
        (41, "Fix quota boundary"),
    ], commits


def validate_compact_ranking(module) -> None:
    commits = [
        module.Commit("a", "docs: explain issue-fix", 40),
        module.Commit("b", "fix: preserve issue-fix evidence", 39),
        module.Commit("c", "feat: add issue-fix lifecycle", 38),
    ]
    grouped = module.classify_commits(commits)
    ranked = grouped["Issue-fix workflow"]
    assert [item.pr_number for item in ranked] == [38, 39, 40], ranked
    bullets = module.bulletize(ranked, limit=2)
    assert bullets[0].startswith("- [#38](https://github.com/huangruiteng/loopx/pull/38)"), bullets
    assert bullets[-1] == "- ...and 1 more merged PR in this theme.", bullets
    note = module.render_note(
        module.Window(module.parse_date("2026-07-01"), module.parse_date("2026-07-14")),
        [*commits, module.Commit("d", "miscellaneous maintenance", 37)],
    )
    assert "Other public changes" not in note, note
    assert "Unclassified maintenance remains available in git history" in note, note


def validate_archive_insertion(module) -> None:
    index = """# Notes

## Latest

- [old](old.md)

## Unrelated

| Window | Note | Focus |
| --- | --- | --- |
| unrelated | row | keep |

## Archive

| Window | Note | Focus |
| --- | --- | --- |
| old | [Read note](old.md) | Old. |

## Publication Rules

Next expected window: 2026-07-01 to 2026-07-14.
"""
    window = module.Window(module.parse_date("2026-07-01"), module.parse_date("2026-07-14"))
    updated = module.replace_latest(index, window)
    updated = module.update_archive(updated, window, "Control plane reliability.")
    row = "| 2026-07-01 to 2026-07-14 | [Read note](2026-07-01-to-2026-07-14.md) |"
    assert updated.count(row) == 1, updated
    archive = updated.split("## Archive", 1)[1].split("## Publication Rules", 1)[0]
    assert row in archive, archive
    unrelated = updated.split("## Unrelated", 1)[1].split("## Archive", 1)[0]
    assert row not in unrelated, unrelated


def main() -> None:
    module = load_generator()
    validate_merged_pr_collection(module)
    validate_compact_ranking(module)
    validate_archive_insertion(module)
    print("update notes generator quality smoke: ok")


if __name__ == "__main__":
    main()
