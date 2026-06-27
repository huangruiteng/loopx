#!/usr/bin/env python3
"""Generate the next public-safe biweekly LoopX update note.

This script is intentionally deterministic and source-limited: it reads the
public repository history plus docs/update-notes/README.md, writes a draft note,
and updates the archive pointers. It does not read LoopX runtime state, chat
history, local private files, raw benchmark traces, or credentials.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / "docs" / "update-notes"
NOTES_INDEX = NOTES_DIR / "README.md"
WINDOW_RE = re.compile(r"(?P<since>\d{4}-\d{2}-\d{2})-to-(?P<until>\d{4}-\d{2}-\d{2})\.md$")


@dataclass(frozen=True)
class Window:
    since: date
    until: date

    @property
    def label(self) -> str:
        return f"{self.since.isoformat()} to {self.until.isoformat()}"

    @property
    def filename(self) -> str:
        return f"{self.since.isoformat()}-to-{self.until.isoformat()}.md"

    @property
    def slug(self) -> str:
        return f"{self.since.isoformat()}-to-{self.until.isoformat()}"

    @property
    def open_after(self) -> date:
        return self.until + timedelta(days=1)

    @property
    def next_window(self) -> "Window":
        next_since = self.until + timedelta(days=1)
        return Window(next_since, next_since + timedelta(days=13))


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


THEMES: list[tuple[str, tuple[str, ...], str]] = [
    (
        "Issue-fix workflow",
        ("issue-fix", "issue fix", "github issue", "review packet"),
        "Issue-fix and PR review flows became more repeatable.",
    ),
    (
        "Benchmark workflow",
        ("skillsbench", "terminal-bench", "benchmark", "harbor", "verifier"),
        "Benchmark and runner contracts became easier to validate and explain.",
    ),
    (
        "Control plane reliability",
        ("quota", "scheduler", "gate", "todo", "task graph", "refresh-state"),
        "Quota, gates, todos, and scheduler behavior became more explicit.",
    ),
    (
        "Host and slash commands",
        ("slash", "host", "codex", "/loopx", "command", "launch"),
        "Host entry points and command contracts became clearer.",
    ),
    (
        "Evented state and read paths",
        ("event", "read path", "projection", "history", "cold-path"),
        "State projection and history read paths moved toward durable contracts.",
    ),
    (
        "Docs and public surface",
        ("docs", "readme", "showcase", "frontstage", "update note", "catalog"),
        "Public docs, showcases, and release communication improved.",
    ),
]


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def note_windows() -> list[Window]:
    windows: list[Window] = []
    for path in NOTES_DIR.glob("*.md"):
        match = WINDOW_RE.match(path.name)
        if not match:
            continue
        windows.append(Window(parse_date(match.group("since")), parse_date(match.group("until"))))
    return sorted(windows, key=lambda item: item.since)


def infer_next_window() -> Window:
    windows = note_windows()
    if not windows:
        anchor = date(2026, 5, 31)
        return Window(anchor, anchor + timedelta(days=13))
    return windows[-1].next_window


def collect_commits(window: Window) -> list[Commit]:
    output = run_git(
        [
            "log",
            f"--since={window.since.isoformat()}T00:00:00",
            f"--until={window.until.isoformat()}T23:59:59",
            "--pretty=format:%h%x09%s",
        ]
    )
    commits: list[Commit] = []
    seen_subjects: set[str] = set()
    for line in output.splitlines():
        if "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        subject = subject.strip()
        if not subject or subject.startswith("Merge pull request "):
            continue
        key = subject.lower()
        if key in seen_subjects:
            continue
        seen_subjects.add(key)
        commits.append(Commit(sha=sha, subject=subject))
    return commits


def classify_commits(commits: list[Commit]) -> dict[str, list[Commit]]:
    grouped: dict[str, list[Commit]] = {theme: [] for theme, _, _ in THEMES}
    grouped["Other public changes"] = []
    for commit in commits:
        lowered = commit.subject.lower()
        for theme, needles, _summary in THEMES:
            if any(needle in lowered for needle in needles):
                grouped[theme].append(commit)
                break
        else:
            grouped["Other public changes"].append(commit)
    return {theme: values for theme, values in grouped.items() if values}


def bulletize(commits: list[Commit], limit: int = 8) -> list[str]:
    bullets = [f"- `{commit.sha}` {commit.subject}" for commit in commits[:limit]]
    remaining = len(commits) - limit
    if remaining > 0:
        bullets.append(f"- ...and {remaining} more public commits in this theme.")
    return bullets


def focus_for(grouped: dict[str, list[Commit]]) -> str:
    themes = [theme for theme in grouped if theme != "Other public changes"]
    if not themes:
        return "Public repository maintenance and documentation."
    return ", ".join(themes[:4]) + "."


def render_note(window: Window, commits: list[Commit]) -> str:
    grouped = classify_commits(commits)
    highlight_lines = []
    for theme, _needles, summary in THEMES:
        if theme in grouped:
            highlight_lines.append(f"- {summary}")
    if grouped.get("Other public changes"):
        highlight_lines.append("- Additional public repository changes shipped in smaller maintenance slices.")
    if not highlight_lines:
        highlight_lines.append("- No public commits were found for this window; review the draft before publishing.")

    sections: list[str] = []
    for theme, values in grouped.items():
        sections.append(f"### {theme}\n\n" + "\n".join(bulletize(values)))
    if not sections:
        sections.append("### Public change review\n\n- No public commits were collected for this window.")

    return "\n".join(
        [
            f"# Biweekly Update Note: {window.label}",
            "",
            "## Source Boundary",
            "",
            f"This note summarizes public repository history from {window.since.isoformat()} "
            f"through {window.until.isoformat()}. It uses public commit history, shipped docs, "
            "examples, and smoke tests. It does not include private operator state, raw "
            "benchmark evidence, private links, local paths, or credentials.",
            "",
            "## Highlights",
            "",
            "\n".join(highlight_lines),
            "",
            "## What Shipped",
            "",
            "\n\n".join(sections),
            "",
            "## Validation And Public Boundary",
            "",
            "This source draft is generated by `scripts/update_notes_release_job.py` from "
            "public git history. The generator does not use an LLM; treat the output as a "
            "factual packet for maintainer or LoopX-agent editing before publication. Before "
            "merging the generated PR, run the update-note smoke, `git diff --check`, and "
            "LoopX public boundary scan over the touched files.",
            "",
            "## Next Window",
            "",
            f"The next expected window is {window.next_window.label}.",
            "",
        ]
    )


def replace_latest(index_text: str, window: Window) -> str:
    latest_line = f"- [{window.label}]({window.filename})"
    pattern = re.compile(r"(## Latest\n\n)(?:- \[[^\n]+\]\([^)]+\)\n?)", re.MULTILINE)
    if pattern.search(index_text):
        return pattern.sub(rf"\1{latest_line}\n", index_text)
    return index_text.replace("## Latest\n\n", f"## Latest\n\n{latest_line}\n\n")


def update_archive(index_text: str, window: Window, focus: str) -> str:
    row = f"| {window.label} | [Read note]({window.filename}) | {focus} |"
    if row in index_text or window.filename in index_text:
        return index_text
    marker = "| --- | --- | --- |\n"
    if marker not in index_text:
        raise SystemExit("docs/update-notes/README.md archive table marker not found")
    return index_text.replace(marker, marker + row + "\n", 1)


def update_next_expected(index_text: str, window: Window) -> str:
    next_label = window.next_window.label
    pattern = re.compile(r"Next expected window: \d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}\.")
    replacement = f"Next expected window: {next_label}."
    if pattern.search(index_text):
        return pattern.sub(replacement, index_text)
    return index_text


def write_github_output(values: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="Window start date, YYYY-MM-DD.")
    parser.add_argument("--until", help="Window end date, YYYY-MM-DD.")
    parser.add_argument("--today", default=date.today().isoformat(), help="Current date for due checks.")
    parser.add_argument("--force", action="store_true", help="Write even before the inferred open-after date.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing note file.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing files.")
    args = parser.parse_args()

    if bool(args.since) != bool(args.until):
        raise SystemExit("--since and --until must be provided together")

    window = (
        Window(parse_date(args.since), parse_date(args.until))
        if args.since and args.until
        else infer_next_window()
    )
    today = parse_date(args.today)
    note_path = NOTES_DIR / window.filename

    if today < window.open_after and not args.force:
        print(f"update notes: window {window.label} is not due until {window.open_after}")
        write_github_output({"changed": "false", "window": window.label, "window_slug": window.slug})
        return

    if note_path.exists() and not args.overwrite:
        print(f"update notes: {note_path.relative_to(ROOT)} already exists")
        write_github_output({"changed": "false", "window": window.label, "window_slug": window.slug})
        return

    commits = collect_commits(window)
    grouped = classify_commits(commits)
    note = render_note(window, commits)
    focus = focus_for(grouped)
    index_text = NOTES_INDEX.read_text(encoding="utf-8")
    index_text = replace_latest(index_text, window)
    index_text = update_archive(index_text, window, focus)
    index_text = update_next_expected(index_text, window)

    print(f"update notes: window={window.label} commits={len(commits)} file={note_path.relative_to(ROOT)}")
    if args.dry_run:
        print(note)
        write_github_output({"changed": "false", "window": window.label, "window_slug": window.slug})
        return

    note_path.write_text(note, encoding="utf-8")
    NOTES_INDEX.write_text(index_text, encoding="utf-8")
    write_github_output(
        {
            "changed": "true",
            "window": window.label,
            "window_slug": window.slug,
            "note_file": str(note_path.relative_to(ROOT)),
        }
    )


if __name__ == "__main__":
    main()
