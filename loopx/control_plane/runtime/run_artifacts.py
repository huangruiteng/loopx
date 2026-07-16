from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ...file_lock import exclusive_file_lock


def run_file_stem(generated_at: str) -> str:
    return re.sub(r"[^0-9A-Za-z-]+", "-", generated_at).strip("-")


def unique_run_artifact_paths(runs_dir: Path, stem: str, suffix: str) -> tuple[Path, Path]:
    candidate = runs_dir / f"{stem}-{suffix}.json"
    markdown_candidate = runs_dir / f"{stem}-{suffix}.md"
    if not candidate.exists() and not markdown_candidate.exists():
        return candidate, markdown_candidate
    index = 2
    while True:
        candidate = runs_dir / f"{stem}-{suffix}-{index}.json"
        markdown_candidate = runs_dir / f"{stem}-{suffix}-{index}.md"
        if not candidate.exists() and not markdown_candidate.exists():
            return candidate, markdown_candidate
        index += 1


def reserve_unique_run_artifact_paths(
    runs_dir: Path,
    stem: str,
    suffix: str,
) -> tuple[Path, Path]:
    """Atomically reserve one JSON/Markdown artifact pair.

    Dry-run callers should keep using :func:`unique_run_artifact_paths`. Execute
    callers use this reservation so concurrent writers cannot both select and
    truncate the same run artifacts.
    """

    runs_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        actual_suffix = suffix if index == 1 else f"{suffix}-{index}"
        json_path = runs_dir / f"{stem}-{actual_suffix}.json"
        markdown_path = runs_dir / f"{stem}-{actual_suffix}.md"
        try:
            json_fd = os.open(json_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            index += 1
            continue
        try:
            markdown_fd = os.open(
                markdown_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            os.close(json_fd)
            json_path.unlink(missing_ok=True)
            index += 1
            continue
        os.close(json_fd)
        os.close(markdown_fd)
        return json_path, markdown_path


def write_unique_run_artifacts(
    *,
    runs_dir: Path,
    stem: str,
    suffix: str,
    record: dict[str, Any],
    markdown: str,
    index_record: dict[str, Any],
) -> tuple[Path, Path, Path]:
    """Reserve, write, and index one run without sharing artifact identity."""

    json_path, markdown_path = reserve_unique_run_artifact_paths(
        runs_dir,
        stem,
        suffix,
    )
    index_path = runs_dir / "index.jsonl"
    index_record["json_path"] = str(json_path)
    index_record["markdown_path"] = str(markdown_path)
    try:
        json_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(markdown.rstrip("\n") + "\n", encoding="utf-8")
        with exclusive_file_lock(index_path):
            with index_path.open("a", encoding="utf-8") as index_file:
                index_file.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    except Exception:
        # No index row refers to the pair until the final append. Remove a
        # failed reservation instead of leaving it looking like a valid run.
        json_path.unlink(missing_ok=True)
        markdown_path.unlink(missing_ok=True)
        raise
    return json_path, markdown_path, index_path
