from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .authority import goal_authority_registry_summary
from .control_plane import compact_control_plane_policy
from .execution_profile import compact_execution_profile
from .paths import resolve_runtime_root
from .quota import goal_quota_with_spend_ledger
from .registry import read_json, registry_goals


STATUS_NEUTRAL_CLASSIFICATIONS = {
    "quota_slot_spent",
}
REGISTRY_ATTENTION_FIELDS = (
    "waiting_on",
    "attention_status",
    "operator_question",
    "recommended_action",
    "next_handoff_condition",
)


def now_local() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def run_file_stem(generated_at: str) -> str:
    return re.sub(r"[^0-9A-Za-z-]+", "-", generated_at).strip("-")


def unique_run_paths(runs_dir: Path, generated_at: str) -> tuple[Path, Path]:
    stem = run_file_stem(generated_at)
    json_path = runs_dir / f"{stem}.json"
    markdown_path = runs_dir / f"{stem}.md"
    if not json_path.exists() and not markdown_path.exists():
        return json_path, markdown_path

    suffix = 2
    while True:
        json_path = runs_dir / f"{stem}-{suffix}.json"
        markdown_path = runs_dir / f"{stem}-{suffix}.md"
        if not json_path.exists() and not markdown_path.exists():
            return json_path, markdown_path
        suffix += 1


def validate_goal_id_path_segment(goal_id: str) -> str:
    value = str(goal_id or "").strip()
    if not value:
        raise ValueError("goal id is required")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("goal id must be a single path segment")
    if Path(value).name != value:
        raise ValueError("goal id must not include path traversal")
    return value


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def discover_goal_ids(
    runtime_root: Path,
    registry: dict[str, Any],
    requested_goal: str | None,
    *,
    include_runtime_goals: bool = True,
) -> list[str]:
    if requested_goal:
        return [requested_goal]

    ids = {str(goal.get("id")) for goal in registry_goals(registry)}
    goals_dir = runtime_root / "goals"
    if include_runtime_goals and goals_dir.exists():
        ids.update(path.name for path in goals_dir.iterdir() if path.is_dir())
    return sorted(ids)


def load_index(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0

    records: list[dict[str, Any]] = []
    positions: dict[tuple[str, str, str], int] = {}
    raw_count = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            raw_count += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue

            key = (
                str(item.get("generated_at") or ""),
                str(item.get("json_path") or ""),
                str(item.get("markdown_path") or ""),
            )
            item = dict(item)
            json_path = Path(str(item.get("json_path") or ""))
            markdown_path = Path(str(item.get("markdown_path") or ""))
            item["json_exists"] = json_path.exists() if str(json_path) else False
            item["markdown_exists"] = markdown_path.exists() if str(markdown_path) else False
            if key in positions:
                records[positions[key]].update(item)
            else:
                positions[key] = len(records)
                records.append(item)
    return records, raw_count


def append_benchmark_run(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    benchmark_run: dict[str, Any],
    classification: str = "benchmark_run_v0",
    recommended_action: str | None = None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    if benchmark_run.get("schema_version") != "benchmark_run_v0":
        raise ValueError("benchmark run must have schema_version=benchmark_run_v0")

    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    generated_at = now_local()
    action = recommended_action or "inspect benchmark_run_v0 summary and continue passive benchmark work"
    health_check = "benchmark_run_v0 compact event public-safe"

    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    json_path, markdown_path = unique_run_paths(runs_dir, generated_at)
    index_path = runs_dir / "index.jsonl"
    record: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "health_check": health_check,
        "benchmark_run": benchmark_run,
    }
    if delivery_batch_scale:
        record["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        record["delivery_outcome"] = delivery_outcome

    index_record = {
        **record,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "generated_at": generated_at,
        "health_check": health_check,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "benchmark_run": benchmark_run,
    }
    if delivery_batch_scale:
        payload["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        payload["delivery_outcome"] = delivery_outcome

    if not dry_run:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_benchmark_run_append_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def append_benchmark_result(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    benchmark_result: dict[str, Any],
    classification: str = "benchmark_result_v0",
    recommended_action: str | None = None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    if benchmark_result.get("schema_version") != "benchmark_result_v0":
        raise ValueError("benchmark result must have schema_version=benchmark_result_v0")

    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    generated_at = now_local()
    action = recommended_action or "inspect benchmark_result_v0 summary and continue benchmark comparison work"
    health_check = "benchmark_result_v0 compact event public-safe"

    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    json_path, markdown_path = unique_run_paths(runs_dir, generated_at)
    index_path = runs_dir / "index.jsonl"
    record: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "health_check": health_check,
        "benchmark_result": benchmark_result,
    }
    if delivery_batch_scale:
        record["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        record["delivery_outcome"] = delivery_outcome

    index_record = {
        **record,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "generated_at": generated_at,
        "health_check": health_check,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "benchmark_result": benchmark_result,
    }
    if delivery_batch_scale:
        payload["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        payload["delivery_outcome"] = delivery_outcome

    if not dry_run:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_benchmark_result_append_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def append_benchmark_comparison(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    benchmark_comparison: dict[str, Any],
    classification: str = "benchmark_comparison_v0",
    recommended_action: str | None = None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    if benchmark_comparison.get("schema_version") != "benchmark_comparison_v0":
        raise ValueError("benchmark comparison must have schema_version=benchmark_comparison_v0")

    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    generated_at = now_local()
    action = recommended_action or "inspect benchmark_comparison_v0 deltas and continue benchmark analysis"
    health_check = "benchmark_comparison_v0 compact event public-safe"

    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    json_path, markdown_path = unique_run_paths(runs_dir, generated_at)
    index_path = runs_dir / "index.jsonl"
    record: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "health_check": health_check,
        "benchmark_comparison": benchmark_comparison,
    }
    if delivery_batch_scale:
        record["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        record["delivery_outcome"] = delivery_outcome

    index_record = {
        **record,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "generated_at": generated_at,
        "health_check": health_check,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "benchmark_comparison": benchmark_comparison,
    }
    if delivery_batch_scale:
        payload["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        payload["delivery_outcome"] = delivery_outcome

    if not dry_run:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_benchmark_comparison_append_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def append_benchmark_experiment_report(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    benchmark_experiment_report: dict[str, Any],
    classification: str = "benchmark_experiment_report_v0",
    recommended_action: str | None = None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    if benchmark_experiment_report.get("schema_version") != "benchmark_experiment_report_v0":
        raise ValueError("benchmark experiment report must have schema_version=benchmark_experiment_report_v0")

    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    generated_at = now_local()
    action = recommended_action or "inspect benchmark_experiment_report_v0 summary and continue report consumer work"
    health_check = "benchmark_experiment_report_v0 compact event public-safe"

    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    json_path, markdown_path = unique_run_paths(runs_dir, generated_at)
    index_path = runs_dir / "index.jsonl"
    record: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "health_check": health_check,
        "benchmark_experiment_report": benchmark_experiment_report,
    }
    if delivery_batch_scale:
        record["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        record["delivery_outcome"] = delivery_outcome

    index_record = {
        **record,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "generated_at": generated_at,
        "health_check": health_check,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "benchmark_experiment_report": benchmark_experiment_report,
    }
    if delivery_batch_scale:
        payload["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        payload["delivery_outcome"] = delivery_outcome

    if not dry_run:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_benchmark_experiment_report_append_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def append_active_user_assisted_pilot(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    active_user_assisted_pilot: dict[str, Any],
    classification: str = "active_user_assisted_pilot_v0",
    recommended_action: str | None = None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    if active_user_assisted_pilot.get("schema_version") != "active_user_assisted_pilot_v0":
        raise ValueError("active user assisted pilot must have schema_version=active_user_assisted_pilot_v0")

    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    generated_at = now_local()
    action = recommended_action or "inspect active_user_assisted_pilot_v0 summary and decide assisted treatment next step"
    health_check = "active_user_assisted_pilot_v0 compact event public-safe"

    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    json_path, markdown_path = unique_run_paths(runs_dir, generated_at)
    index_path = runs_dir / "index.jsonl"
    record: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "health_check": health_check,
        "active_user_assisted_pilot": active_user_assisted_pilot,
    }
    if delivery_batch_scale:
        record["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        record["delivery_outcome"] = delivery_outcome

    index_record = {
        **record,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_id": safe_goal_id,
        "classification": classification,
        "recommended_action": action,
        "generated_at": generated_at,
        "health_check": health_check,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "active_user_assisted_pilot": active_user_assisted_pilot,
    }
    if delivery_batch_scale:
        payload["delivery_batch_scale"] = delivery_batch_scale
    if delivery_outcome:
        payload["delivery_outcome"] = delivery_outcome

    if not dry_run:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_active_user_assisted_pilot_append_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def latest_status_run(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    for run in runs:
        if str(run.get("classification") or "") in STATUS_NEUTRAL_CLASSIFICATIONS:
            continue
        return run
    return None


def collect_history(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str | None,
    limit: int,
    include_runtime_goals: bool = True,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    goal_meta = {str(goal.get("id")): goal for goal in registry_goals(registry)}
    goals: list[dict[str, Any]] = []
    all_runs: list[dict[str, Any]] = []

    for current_goal_id in discover_goal_ids(
        runtime_root,
        registry,
        goal_id,
        include_runtime_goals=include_runtime_goals,
    ):
        index_path = runtime_root / "goals" / current_goal_id / "runs" / "index.jsonl"
        runs, raw_count = load_index(index_path)
        runs = [
            run
            for _, run in sorted(
                enumerate(runs),
                key=lambda item: (str(item[1].get("generated_at") or ""), item[0]),
                reverse=True,
            )
        ]
        for run in runs:
            run["goal_id"] = str(run.get("goal_id") or current_goal_id)
        all_runs.extend(runs)

        registry_member = current_goal_id in goal_meta
        meta = goal_meta.get(current_goal_id) or {}
        adapter = meta.get("adapter") if isinstance(meta.get("adapter"), dict) else {}
        quota = goal_quota_with_spend_ledger(meta, runs) if registry_member else None
        goal_record = {
            "id": current_goal_id,
            "domain": meta.get("domain"),
            "status": meta.get("status") if registry_member else "legacy-runtime",
            "repo": meta.get("repo") if registry_member else None,
            "state_file": meta.get("state_file") if registry_member else None,
            "registry_member": registry_member,
            "legacy_runtime_goal": not registry_member,
            "adapter_kind": adapter.get("kind"),
            "adapter_status": adapter.get("status"),
            "coordination": meta.get("coordination") if isinstance(meta.get("coordination"), dict) else None,
            "spawn_policy": meta.get("spawn_policy") if isinstance(meta.get("spawn_policy"), dict) else None,
            "execution_profile": compact_execution_profile(meta.get("execution_profile")) if registry_member else None,
            "control_plane": compact_control_plane_policy(meta.get("control_plane")) if registry_member else None,
            "guards": meta.get("guards") if isinstance(meta.get("guards"), list) else [],
            "next_probe": meta.get("next_probe") if registry_member else None,
            "authority_registry": goal_authority_registry_summary(meta) if registry_member else None,
            "quota": quota,
            "index_path": str(index_path),
            "index_exists": index_path.exists(),
            "raw_index_records": raw_count,
            "unique_runs": len(runs),
            "latest_status_run": latest_status_run(runs),
            "latest_runs": runs[:limit],
        }
        if registry_member:
            for field in REGISTRY_ATTENTION_FIELDS:
                if meta.get(field):
                    goal_record[field] = meta.get(field)
        goals.append(goal_record)

    all_runs.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    return {
        "ok": True,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_filter": goal_id,
        "goal_count": len(goals),
        "run_count": len(all_runs),
        "goals": goals,
        "runs": all_runs[:limit],
    }


def render_history_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "# Goal Harness Run History\n\n- ok: `False`\n- error: " + str(payload.get("error"))

    lines = [
        "# Goal Harness Run History",
        "",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- goal_filter: `{payload.get('goal_filter')}`",
        f"- goals: `{payload.get('goal_count')}`",
        f"- unique_runs: `{payload.get('run_count')}`",
        "",
        "| generated_at | goal | classification | files | action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for run in payload.get("runs") or []:
        action = str(run.get("recommended_action") or "").replace("|", "\\|")
        lines.append(
            "| "
            f"`{run.get('generated_at')}` | "
            f"`{run.get('goal_id')}` | "
            f"`{run.get('classification')}` | "
            f"{run.get('json_exists')}/{run.get('markdown_exists')} | "
            f"{action} |"
        )

    lines.extend(["", "## Goals"])
    for goal in payload.get("goals") or []:
        lines.append(
            "- "
            f"`{goal.get('id')}`: status=`{goal.get('status')}`, "
            f"registry_member=`{goal.get('registry_member')}`, "
            f"adapter=`{goal.get('adapter_kind')}:{goal.get('adapter_status')}`, "
            f"index_exists=`{goal.get('index_exists')}`, "
            f"records=`{goal.get('raw_index_records')}`, "
            f"unique_runs=`{goal.get('unique_runs')}`"
        )
    return "\n".join(lines)


def render_benchmark_run_append_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Benchmark Run Append",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
    ]
    if payload.get("json_path"):
        lines.append(f"- json_path: `{payload.get('json_path')}`")
    if payload.get("index_path"):
        lines.append(f"- index_path: `{payload.get('index_path')}`")
    if payload.get("recommended_action"):
        lines.append(f"- recommended_action: {payload.get('recommended_action')}")
    benchmark_run = payload.get("benchmark_run") if isinstance(payload.get("benchmark_run"), dict) else {}
    if benchmark_run:
        progress = benchmark_run.get("progress") if isinstance(benchmark_run.get("progress"), dict) else {}
        metrics = benchmark_run.get("metrics") if isinstance(benchmark_run.get("metrics"), dict) else {}
        lines.extend(
            [
                "",
                "## Benchmark Run",
                "",
                f"- schema_version: `{benchmark_run.get('schema_version')}`",
                f"- benchmark_id: `{benchmark_run.get('benchmark_id')}`",
                f"- source_runner: `{benchmark_run.get('source_runner')}`",
                f"- mode: `{benchmark_run.get('mode')}`",
                f"- progress: completed={progress.get('n_completed_trials')} total={progress.get('n_total_trials')}",
                f"- metrics: input_tokens={metrics.get('input_tokens')} output_tokens={metrics.get('output_tokens')} cost_usd={metrics.get('cost_usd')}",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines)


def render_benchmark_result_append_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Benchmark Result Append",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
    ]
    if payload.get("json_path"):
        lines.append(f"- json_path: `{payload.get('json_path')}`")
    if payload.get("index_path"):
        lines.append(f"- index_path: `{payload.get('index_path')}`")
    if payload.get("recommended_action"):
        lines.append(f"- recommended_action: {payload.get('recommended_action')}")
    benchmark_result = (
        payload.get("benchmark_result")
        if isinstance(payload.get("benchmark_result"), dict)
        else {}
    )
    if benchmark_result:
        official = (
            benchmark_result.get("official_task_score")
            if isinstance(benchmark_result.get("official_task_score"), dict)
            else {}
        )
        control = (
            benchmark_result.get("control_plane_score")
            if isinstance(benchmark_result.get("control_plane_score"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Benchmark Result",
                "",
                f"- schema_version: `{benchmark_result.get('schema_version')}`",
                f"- task_id: `{benchmark_result.get('task_id')}`",
                f"- scenario_id: `{benchmark_result.get('scenario_id')}`",
                f"- terminal_state: `{benchmark_result.get('terminal_state')}`",
                f"- official_task_score: kind={official.get('kind')} value={official.get('value')} passed={official.get('passed')}",
                f"- control_plane_score: schema={control.get('schema_version')} kind={control.get('kind')} value={control.get('value')} aggregation={control.get('aggregation')}",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines)


def render_benchmark_comparison_append_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Benchmark Comparison Append",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
    ]
    if payload.get("json_path"):
        lines.append(f"- json_path: `{payload.get('json_path')}`")
    if payload.get("index_path"):
        lines.append(f"- index_path: `{payload.get('index_path')}`")
    if payload.get("recommended_action"):
        lines.append(f"- recommended_action: {payload.get('recommended_action')}")
    benchmark_comparison = (
        payload.get("benchmark_comparison")
        if isinstance(payload.get("benchmark_comparison"), dict)
        else {}
    )
    if benchmark_comparison:
        lines.extend(
            [
                "",
                "## Benchmark Comparison",
                "",
                f"- schema_version: `{benchmark_comparison.get('schema_version')}`",
                f"- task_id: `{benchmark_comparison.get('task_id')}`",
                f"- comparison_id: `{benchmark_comparison.get('comparison_id')}`",
                f"- official_task_score_delta: `{benchmark_comparison.get('official_task_score_delta')}`",
                f"- control_plane_score_delta: `{benchmark_comparison.get('control_plane_score_delta')}`",
                f"- both_success: `{benchmark_comparison.get('both_success')}`",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines)


def render_benchmark_experiment_report_append_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Benchmark Experiment Report Append",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
    ]
    if payload.get("json_path"):
        lines.append(f"- json_path: `{payload.get('json_path')}`")
    if payload.get("index_path"):
        lines.append(f"- index_path: `{payload.get('index_path')}`")
    if payload.get("recommended_action"):
        lines.append(f"- recommended_action: {payload.get('recommended_action')}")
    benchmark_report = (
        payload.get("benchmark_experiment_report")
        if isinstance(payload.get("benchmark_experiment_report"), dict)
        else {}
    )
    if benchmark_report:
        identity = (
            benchmark_report.get("experiment_identity")
            if isinstance(benchmark_report.get("experiment_identity"), dict)
            else {}
        )
        official = (
            benchmark_report.get("official_score")
            if isinstance(benchmark_report.get("official_score"), dict)
            else {}
        )
        negative = (
            benchmark_report.get("negative_results")
            if isinstance(benchmark_report.get("negative_results"), dict)
            else {}
        )
        next_decision = (
            benchmark_report.get("next_decision")
            if isinstance(benchmark_report.get("next_decision"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Benchmark Experiment Report",
                "",
                f"- schema_version: `{benchmark_report.get('schema_version')}`",
                f"- report_id: `{identity.get('report_id')}`",
                f"- benchmark_id: `{identity.get('benchmark_id')}`",
                f"- official_delta: `{official.get('delta')}`",
                f"- submit_eligible: `{official.get('submit_eligible')}`",
                f"- leaderboard_evidence: `{official.get('leaderboard_evidence')}`",
                f"- null_official_delta: `{negative.get('null_official_delta')}`",
                f"- negative_evidence_layers: `{negative.get('negative_evidence_layers')}`",
                f"- next_decision: `{next_decision.get('decision')}`",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines)


def render_active_user_assisted_pilot_append_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Active User Assisted Pilot Append",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
    ]
    if payload.get("json_path"):
        lines.append(f"- json_path: `{payload.get('json_path')}`")
    if payload.get("index_path"):
        lines.append(f"- index_path: `{payload.get('index_path')}`")
    if payload.get("recommended_action"):
        lines.append(f"- recommended_action: {payload.get('recommended_action')}")

    pilot = (
        payload.get("active_user_assisted_pilot")
        if isinstance(payload.get("active_user_assisted_pilot"), dict)
        else {}
    )
    if pilot:
        trigger = pilot.get("trigger") if isinstance(pilot.get("trigger"), dict) else {}
        operator_run = (
            pilot.get("operator_simulator_run")
            if isinstance(pilot.get("operator_simulator_run"), dict)
            else {}
        )
        next_decision = (
            pilot.get("next_run_decision")
            if isinstance(pilot.get("next_run_decision"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Active User Assisted Pilot",
                "",
                f"- schema_version: `{pilot.get('schema_version')}`",
                f"- pilot_id: `{pilot.get('pilot_id')}`",
                f"- benchmark_id: `{pilot.get('benchmark_id')}`",
                f"- task_id: `{pilot.get('task_id')}`",
                f"- trigger_kind: `{trigger.get('kind')}`",
                f"- failed_autonomous_mode_count: `{trigger.get('failed_autonomous_mode_count')}`",
                f"- assisted_score_kind: `{trigger.get('assisted_score_kind')}`",
                f"- operator_run_schema: `{operator_run.get('schema_version')}`",
                f"- proactive_intervention_count: `{operator_run.get('proactive_intervention_count')}`",
                f"- no_oracle_audit_passed: `{operator_run.get('no_oracle_audit_passed')}`",
                f"- side_effect_audit_passed: `{operator_run.get('side_effect_audit_passed')}`",
                f"- official_task_score_kind: `{operator_run.get('official_task_score_kind')}`",
                f"- next_decision: `{next_decision.get('decision')}`",
                f"- keep_official_scores_separate: `{next_decision.get('keep_official_scores_separate')}`",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines)
