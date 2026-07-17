from __future__ import annotations

import os
import re
from pathlib import Path


def run_file_stem(generated_at: str) -> str:
    return re.sub(r"[^0-9A-Za-z-]+", "-", generated_at).strip("-")


def _run_artifact_candidates(
    runs_dir: Path,
    stem: str,
    suffix: str | None,
    index: int,
) -> tuple[Path, Path]:
    base_stem = f"{stem}-{suffix}" if suffix else stem
    actual_stem = base_stem if index == 1 else f"{base_stem}-{index}"
    return (
        runs_dir / f"{actual_stem}.json",
        runs_dir / f"{actual_stem}.md",
    )


def next_run_artifact_paths(
    runs_dir: Path,
    stem: str,
    suffix: str | None = None,
) -> tuple[Path, Path]:
    """Preview the next artifact pair without reserving it."""

    index = 1
    while True:
        candidate, markdown_candidate = _run_artifact_candidates(
            runs_dir,
            stem,
            suffix,
            index,
        )
        if not candidate.exists() and not markdown_candidate.exists():
            return candidate, markdown_candidate
        index += 1


def reserve_run_artifact_paths(
    runs_dir: Path,
    stem: str,
    suffix: str | None = None,
) -> tuple[Path, Path]:
    """Atomically reserve one JSON/Markdown artifact pair across processes.

    The JSON path is the reservation sentinel. Writers must call this only for
    an executing append, then replace the empty sentinel with the final JSON.
    A pre-existing Markdown file also excludes the pair so a partial legacy
    artifact is never overwritten.
    """

    runs_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate, markdown_candidate = _run_artifact_candidates(
            runs_dir,
            stem,
            suffix,
            index,
        )
        if markdown_candidate.exists():
            index += 1
            continue
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            index += 1
            continue
        else:
            os.close(fd)
            return candidate, markdown_candidate
