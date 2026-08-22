from __future__ import annotations

import argparse
import json
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..deepresearch import (
    DEFAULT_MAX_SOURCES,
    DEFAULT_MAX_SUBQUESTIONS,
    add_source,
    add_subquestion,
    build_packet,
    close_research,
    load_state,
    resolve_contradiction,
    resolve_question,
    start_research,
    write_report,
)
from ..file_lock import LockAcquireTimeoutError, lock_timeout_error_fields

PrintPayload = Callable[..., None]
FormatSelector = Callable[[argparse.Namespace], str]

_ACTIONS = (
    "start",
    "status",
    "add-source",
    "add-subquestion",
    "resolve-question",
    "resolve-contradiction",
    "close",
    "report",
)


def _parse_claims_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"--claims-json is not valid JSON: {error}") from error
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("--claims-json must be a JSON array of claim objects")
    return data


def _parse_contradiction_resolutions(values: list[str] | None) -> list[dict[str, Any]]:
    resolutions: list[dict[str, Any]] = []
    for raw in values or []:
        tokens = shlex.split(raw)
        fields: dict[str, str] = {}
        key: str | None = None
        for token in tokens:
            if token.startswith("--") and "=" not in token:
                key = token[2:].replace("-", "_")
            elif token.startswith("--") and "=" in token:
                name, value = token[2:].split("=", 1)
                fields[name.replace("-", "_")] = value
            elif "=" in token:
                name, value = token.split("=", 1)
                fields[name.replace("-", "_")] = value
            elif key is not None:
                fields[key] = token
                key = None
            else:
                raise ValueError(
                    f"unexpected token {token!r} in --contradiction-resolution; use "
                    "'contradiction-id=<x> sides-with=<claim> rationale=<why>'"
                )
        if "contradiction_id" not in fields or "sides_with" not in fields:
            raise ValueError(
                f"--contradiction-resolution needs 'contradiction-id=<x> sides-with=<claim> "
                f"rationale=<why>'; got {raw!r}"
            )
        fields.setdefault("rationale", "")
        resolutions.append(fields)
    return resolutions


def register_deepresearch_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "deepresearch",
        help="Bounded deep-research loop: packet-driven expeditions, evidence ledgers, "
        "citation-auditable report (/loopx-deepresearch).",
    )
    actions = parser.add_subparsers(dest="deepresearch_action", metavar="{start,status,add-source,add-subquestion,resolve-question,report}")

    def action(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = actions.add_parser(name, help=help_text)
        sub.add_argument(
            "--project",
            default=".",
            help="Project directory holding .loopx/deepresearch/. Defaults to the current directory.",
        )
        add_subcommand_format(sub)
        return sub

    start = action("start", "Start a new bounded deep research for this project.")
    start.add_argument("--question", required=True, help="The main research question.")
    start.add_argument(
        "--max-sources",
        type=int,
        default=DEFAULT_MAX_SOURCES,
        help=f"Source budget. Defaults to {DEFAULT_MAX_SOURCES}.",
    )
    start.add_argument(
        "--max-subquestions",
        type=int,
        default=DEFAULT_MAX_SUBQUESTIONS,
        help=f"Subquestion budget. Defaults to {DEFAULT_MAX_SUBQUESTIONS}.",
    )
    start.add_argument(
        "--new-run",
        action="store_true",
        help=(
            "When the current run has already stopped, close and archive it, then start "
            "fresh. An active (not stopped) run still requires an explicit "
            "`deepresearch close` first."
        ),
    )

    action("status", "Emit the expedition packet: contract, ledgers, next expedition, stop conditions.")

    add_source_parser = action("add-source", "Record one consulted source and the claims extracted from it.")
    add_source_parser.add_argument("--url-or-path", required=True)
    add_source_parser.add_argument(
        "--tool",
        default="unspecified",
        help="Tool that produced the evidence: web_search, web_fetch, local_read, ...",
    )
    add_source_parser.add_argument("--title", help="Optional human-readable source title.")
    add_source_parser.add_argument(
        "--claims-json",
        help='JSON array: [{"text": "...", "stance": "supports|neutral|contradicts|refines", "relates_claim": "c1"|null}]',
    )

    add_subquestion_parser = action("add-subquestion", "Open a subquestion derived from a recorded claim.")
    add_subquestion_parser.add_argument("--text", required=True)
    add_subquestion_parser.add_argument("--priority", choices=("P0", "P1", "P2"), default="P1")
    add_subquestion_parser.add_argument(
        "--from-claim",
        required=True,
        help="Claim id this subquestion derives from; required so lineage cannot be bypassed.",
    )

    resolve_parser = action("resolve-question", "Answer a recorded question citing recorded evidence claims.")
    resolve_parser.add_argument("--question-id", required=True)
    resolve_parser.add_argument("--answer", required=True)
    resolve_parser.add_argument(
        "--evidence-claims",
        nargs="+",
        required=True,
        help="Recorded claim ids backing the answer (space separated).",
    )
    resolve_parser.add_argument(
        "--contradiction-resolution",
        action="append",
        help="'contradiction-id=x1 sides-with=c2 rationale=\"why\"' — required for open "
        "contradictions touching your evidence.",
    )

    contradiction_parser = action(
        "resolve-contradiction",
        "Close one open contradiction standalone with an explicit sides-with rationale.",
    )
    contradiction_parser.add_argument("--contradiction-id", required=True)
    contradiction_parser.add_argument(
        "--sides-with",
        required=True,
        help="The claim id the evidence actually supports.",
    )
    contradiction_parser.add_argument("--rationale", required=True)

    close_parser = action(
        "close",
        "Terminal transition: close this research run so the next question can start.",
    )
    close_parser.add_argument(
        "--note",
        help="Optional close rationale (budget blown, abandoned, complete, ...).",
    )

    action("report", "Render the citation-auditable markdown report and write it next to the state.")


def handle_deepresearch_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "deepresearch":
        return None
    action = getattr(args, "deepresearch_action", None)
    if action is None:
        raise ValueError("deepresearch requires an action: " + ", ".join(_ACTIONS))
    project = Path(getattr(args, "project", ".")).expanduser().resolve()

    def emit(payload: dict[str, Any]) -> int:
        print_payload(payload, output_format(args), lambda data: _render_markdown(data))
        return 0 if payload.get("ok") is True else 1

    try:
        if action == "start":
            state = start_research(
                project,
                question=args.question,
                max_sources=args.max_sources,
                max_subquestions=args.max_subquestions,
                new_run=bool(getattr(args, "new_run", False)),
            )
            return emit(
                {
                    "ok": True,
                    "schema_version": "loopx_deepresearch_started_v0",
                    "question": state["question"],
                    "state_path": str(project / ".loopx" / "deepresearch" / "research.json"),
                    "packet": build_packet(state, cli_bin="loopx", project=project),
                }
            )
        if action == "close":
            result = close_research(project, note=args.note)
            return emit(
                {
                    "ok": True,
                    "schema_version": "loopx_deepresearch_closed_v0",
                    "run_status": result["status"],
                    "closed_at": result["closed_at"],
                    "packet": build_packet(result["state"], cli_bin="loopx", project=project),
                }
            )
        if action == "status":
            state = load_state(project)
            if state is None:
                return emit(
                    {
                        "ok": False,
                        "error": "no active deepresearch state in this project; run "
                        "`loopx deepresearch start --question <text>` first",
                    }
                )
            return emit(
                {
                    "ok": True,
                    "packet": build_packet(state, cli_bin="loopx", project=project),
                }
            )
        if action == "add-source":
            result = add_source(
                project,
                url_or_path=args.url_or_path,
                tool=args.tool,
                title=args.title,
                claims=_parse_claims_json(args.claims_json),
            )
            return emit(
                {
                    "ok": True,
                    "schema_version": "loopx_deepresearch_source_added_v0",
                    "source_id": result["source_id"],
                    "claim_ids": result["claim_ids"],
                    "packet": build_packet(result["state"], cli_bin="loopx", project=project),
                }
            )
        if action == "add-subquestion":
            result = add_subquestion(
                project,
                text=args.text,
                priority=args.priority,
                from_claim=args.from_claim,
            )
            return emit(
                {
                    "ok": True,
                    "schema_version": "loopx_deepresearch_subquestion_added_v0",
                    "question_id": result["question_id"],
                    "packet": build_packet(result["state"], cli_bin="loopx", project=project),
                }
            )
        if action == "resolve-question":
            result = resolve_question(
                project,
                question_id=args.question_id,
                answer=args.answer,
                evidence_claims=list(args.evidence_claims),
                contradiction_resolutions=_parse_contradiction_resolutions(
                    args.contradiction_resolution
                ),
            )
            return emit(
                {
                    "ok": True,
                    "schema_version": "loopx_deepresearch_question_resolved_v0",
                    "question_id": result["question_id"],
                    "packet": build_packet(result["state"], cli_bin="loopx", project=project),
                }
            )
        if action == "resolve-contradiction":
            result = resolve_contradiction(
                project,
                contradiction_id=args.contradiction_id,
                sides_with=args.sides_with,
                rationale=args.rationale,
            )
            return emit(
                {
                    "ok": True,
                    "schema_version": "loopx_deepresearch_contradiction_resolved_v0",
                    "contradiction_id": result["contradiction_id"],
                    "packet": build_packet(result["state"], cli_bin="loopx", project=project),
                }
            )
        if action == "report":
            result = write_report(project)
            return emit(
                {
                    "ok": True,
                    "schema_version": result["schema_version"],
                    "report_path": result["path"],
                    "stop_conditions": result["stop_conditions"],
                    "content": result["content"],
                }
            )
        raise ValueError(f"unknown deepresearch action: {action}")
    except (ValueError, LockAcquireTimeoutError) as error:
        payload: dict[str, Any] = {"ok": False, "error": str(error), "action": action}
        # Lock contention is an operational condition, not a crash: the JSON
        # contract must stay machine-consumable instead of leaking a traceback.
        payload.update(lock_timeout_error_fields(error))
        return emit(payload)


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# LoopX Deepresearch", ""]
    action = payload.get("action") or "packet"
    lines.append(f"- action: `{action}`")
    lines.append(f"- ok: `{payload.get('ok')}`")
    if payload.get("error"):
        lines.append(f"- error: {payload['error']}")
    packet = payload.get("packet")
    if packet is not None:
        stop = packet.get("stop_conditions", {})
        summary = packet.get("ledger_summary", {})
        lines.append(
            f"- ledgers: questions open/answered {summary.get('questions')}, "
            f"sources {summary.get('sources')}, claims {summary.get('claims')}, "
            f"open contradictions {summary.get('open_contradictions')}"
        )
        lines.append(f"- stopped: `{stop.get('stopped')}` ({'; '.join(stop.get('reasons', [])) or 'not yet'})")
        expedition = packet.get("next_expedition")
        if expedition:
            lines.append(
                f"- next expedition: {expedition['question_id']} — {expedition['text']}"
            )
    if payload.get("report_path"):
        lines.append(f"- report: {payload['report_path']}")
    return "\n".join(lines) + "\n"
