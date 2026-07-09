from __future__ import annotations

import json
import shlex
import subprocess
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable

from ..file_lock import exclusive_file_lock
from .artifacts import materialize_public_benchmark_artifacts


RemoteCommandRunner = Callable[[str, float], subprocess.CompletedProcess[str]]

REMOTE_PUBLIC_ARTIFACT_COLLECTOR = r'''
import base64
import glob
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1]).expanduser().resolve()
max_bytes = int(sys.argv[2])
records = []
blocked = 0
seen = set()
for pattern in sys.argv[3:]:
    pure = PurePosixPath(pattern)
    if pure.is_absolute() or ".." in pure.parts:
        blocked += 1
        continue
    for raw_path in sorted(glob.glob(str(root / pattern), recursive=True)):
        path = Path(raw_path)
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(root).as_posix()
        except (OSError, ValueError):
            blocked += 1
            continue
        lower = "/" + relative.lower().lstrip("/")
        public_name = resolved.name.lower().endswith((".compact.json", ".public.json"))
        private = any(marker in lower for marker in (
            "/private/", "/raw/", "/logs/", "/screenshots/", "/agent/",
            "trajectory", "credential", "secret",
        ))
        if not public_name or private or relative in seen:
            blocked += 1
            continue
        try:
            content = resolved.read_bytes()
        except OSError:
            blocked += 1
            continue
        if len(content) > max_bytes:
            blocked += 1
            continue
        seen.add(relative)
        records.append({
            "relative_path": relative,
            "content_base64": base64.b64encode(content).decode("ascii"),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
print(json.dumps({
    "schema_version": "benchmark_remote_public_artifact_collection_v0",
    "artifacts": records,
    "matched_count": len(records),
    "blocked_count": blocked,
}, sort_keys=True))
'''


def build_remote_benchmark_closeout_contract(
    *,
    requested: bool,
    ledger_requested: bool,
    aggregate_requested: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_remote_public_artifact_sync_v0",
        "requested": requested,
        "attempted": False,
        "ok": False,
        "matched_count": 0,
        "written_count": 0,
        "blocked_count": 0,
        "raw_paths_recorded": False,
        "raw_remote_output_recorded": False,
        "raw_task_text_read": False,
        "raw_logs_read": False,
        "raw_trajectory_read": False,
        "local_ledger_update": {
            "requested": ledger_requested,
            "updated": False,
            "compact_count": 0,
            "raw_paths_recorded": False,
        },
        "local_aggregate_update": {
            "requested": aggregate_requested,
            "updated": False,
            "raw_paths_recorded": False,
        },
    }


def _collection_command(
    *,
    remote_root: str,
    artifact_globs: list[str],
    max_bytes: int,
) -> str:
    command = ["python3", "-", remote_root, str(max(1, max_bytes)), *artifact_globs]
    return (
        " ".join(shlex.quote(value) for value in command)
        + " <<'PY'\n"
        + REMOTE_PUBLIC_ARTIFACT_COLLECTOR.strip()
        + "\nPY"
    )


def _refresh_ledger_and_aggregate(
    *,
    public_artifact_dir: Path,
    ledger_path: str,
    run_group_id: str,
    aggregate_path: str,
    canonical_case_ids_file: str,
    benchmark_id: str,
    target_lane_id: str,
    target_run_group_contains: list[str],
    target_backfill_run_group_contains: list[str],
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger_payload = {
        "requested": bool(ledger_path),
        "updated": False,
        "compact_count": 0,
        "raw_paths_recorded": False,
    }
    aggregate_payload = {
        "requested": bool(aggregate_path),
        "updated": False,
        "raw_paths_recorded": False,
    }
    if not ledger_path:
        return ledger_payload, aggregate_payload

    from ..benchmark_ledger import (
        build_benchmark_run_ledger_current_aggregate,
        load_benchmark_run_ledger,
        update_benchmark_run_ledger,
    )

    compact_paths = sorted(public_artifact_dir.rglob("benchmark_run.compact.json"))
    updated = 0
    skipped = 0
    for compact_path in compact_paths:
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        if not isinstance(compact, dict):
            skipped += 1
            continue
        update = update_benchmark_run_ledger(
            ledger_path=Path(ledger_path).expanduser(),
            benchmark_run=compact,
            run_group_id=run_group_id or None,
            notes="remote batch compact/public closeout sync",
            dry_run=False,
            cwd=repo_root,
        )
        if update.get("updated") is True:
            updated += 1
        else:
            skipped += 1
    ledger_payload.update(
        compact_count=len(compact_paths),
        upserted_count=updated,
        skipped_count=skipped,
        updated=bool(updated),
    )

    if not aggregate_path:
        return ledger_payload, aggregate_payload
    canonical_ids = [
        line.strip()
        for line in Path(canonical_case_ids_file)
        .expanduser()
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    ledger = load_benchmark_run_ledger(Path(ledger_path).expanduser())
    aggregate = build_benchmark_run_ledger_current_aggregate(
        ledger,
        benchmark_id=benchmark_id,
        canonical_case_ids=canonical_ids,
        target_lane_id=target_lane_id or None,
        target_run_group_contains=target_run_group_contains,
        target_backfill_run_group_contains=target_backfill_run_group_contains,
    )
    output = Path(aggregate_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    summary = aggregate.get("countable_score_summary")
    if not isinstance(summary, dict):
        summary = {}
    aggregate_payload.update(
        updated=True,
        canonical_total=aggregate.get("canonical_total"),
        countable_case_count=summary.get("countable_case_count"),
        countable_score_sum=summary.get("countable_score_sum"),
        countable_score_mean=summary.get("countable_score_mean"),
        blocked_uncountable_count=len(
            aggregate.get("blocked_uncountable_case_ids") or []
        ),
        runnable_case_count=len(aggregate.get("runnable_case_ids") or []),
    )
    return ledger_payload, aggregate_payload


def closeout_remote_benchmark_batch(
    *,
    run_remote_command: RemoteCommandRunner,
    remote_root: str,
    artifact_globs: list[str],
    local_public_artifact_dir: str | Path,
    adapter_kind: str,
    max_bytes: int,
    sync_timeout_sec: float,
    ledger_path: str = "",
    run_group_id: str = "",
    aggregate_path: str = "",
    canonical_case_ids_file: str = "",
    benchmark_id: str = "",
    target_lane_id: str = "",
    target_run_group_contains: list[str] | None = None,
    target_backfill_run_group_contains: list[str] | None = None,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    requested = bool(remote_root or artifact_globs or local_public_artifact_dir)
    payload = build_remote_benchmark_closeout_contract(
        requested=requested,
        ledger_requested=bool(ledger_path),
        aggregate_requested=bool(aggregate_path),
    )
    if not requested:
        return payload
    payload["attempted"] = True
    try:
        proc = run_remote_command(
            _collection_command(
                remote_root=remote_root,
                artifact_globs=artifact_globs,
                max_bytes=max_bytes,
            ),
            sync_timeout_sec,
        )
    except subprocess.TimeoutExpired:
        payload["first_blocker"] = "public_artifact_sync_timeout"
        return payload
    except OSError:
        payload["first_blocker"] = "public_artifact_sync_launch_failed"
        return payload
    if proc.returncode != 0:
        payload["first_blocker"] = "public_artifact_sync_remote_exit_nonzero"
        payload["remote_exit_code"] = proc.returncode
        return payload
    try:
        collected = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        payload["first_blocker"] = "public_artifact_sync_payload_missing"
        return payload
    artifacts = collected.get("artifacts") if isinstance(collected, dict) else None
    if not isinstance(artifacts, list):
        payload["first_blocker"] = "public_artifact_sync_payload_invalid"
        return payload

    local_dir = Path(local_public_artifact_dir).expanduser()
    materialized = materialize_public_benchmark_artifacts(
        artifacts,
        output_dir=local_dir,
        adapter_kind=adapter_kind,
        max_bytes=max_bytes,
    )
    payload.update(
        matched_count=int(collected.get("matched_count") or 0),
        written_count=int(materialized.get("written_count") or 0),
        blocked_count=(
            int(collected.get("blocked_count") or 0)
            + int(materialized.get("blocked_count") or 0)
        ),
        written_artifact_basenames=materialized.get(
            "written_artifact_basenames", []
        ),
    )
    if materialized.get("ok") is not True:
        payload["first_blocker"] = "public_artifact_materialization_failed"
        payload["blocked_reasons"] = materialized.get("blocked_reasons", {})
        return payload
    try:
        closeout_path = (
            Path(ledger_path).expanduser().with_suffix(
                Path(ledger_path).expanduser().suffix + ".closeout"
            )
            if ledger_path
            else None
        )
        lock = (
            exclusive_file_lock(closeout_path)
            if closeout_path is not None
            else nullcontext()
        )
        with lock:
            ledger_update, aggregate_update = _refresh_ledger_and_aggregate(
                public_artifact_dir=local_dir,
                ledger_path=ledger_path,
                run_group_id=run_group_id,
                aggregate_path=aggregate_path,
                canonical_case_ids_file=canonical_case_ids_file,
                benchmark_id=benchmark_id,
                target_lane_id=target_lane_id,
                target_run_group_contains=list(target_run_group_contains or []),
                target_backfill_run_group_contains=list(
                    target_backfill_run_group_contains or []
                ),
                repo_root=Path(repo_root),
            )
    except (OSError, TimeoutError, ValueError, TypeError, json.JSONDecodeError) as exc:
        payload["first_blocker"] = "public_artifact_local_closeout_failed"
        payload["local_closeout_error_type"] = type(exc).__name__[:80]
        return payload
    payload["local_ledger_update"] = ledger_update
    payload["local_aggregate_update"] = aggregate_update
    if ledger_path and int(ledger_update.get("compact_count") or 0) == 0:
        payload["first_blocker"] = "benchmark_compact_missing_after_remote_closeout"
        return payload
    payload["ok"] = True
    return payload
