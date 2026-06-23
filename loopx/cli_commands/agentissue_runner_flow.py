from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.agentissue import (
    AGENTISSUE_BENCHMARK_ID,
    AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION,
    AGENTISSUE_DEFAULT_TAG,
    build_agentissue_codex_cli_runner_wrapper,
    materialize_agentissue_codex_cli_runner_execution_gate,
    materialize_agentissue_codex_cli_runner_first_run_handoff,
    materialize_agentissue_codex_cli_runner_private_script,
    materialize_agentissue_codex_cli_runner_real_result,
    materialize_agentissue_codex_cli_runner_run_gate,
    materialize_agentissue_codex_cli_runner_synthetic_staging,
    materialize_agentissue_codex_cli_runner_target_handoff,
    materialize_agentissue_codex_cli_runner_workflow_check,
)
from ..delivery_batch_scale import DELIVERY_BATCH_SCALE_CHOICES
from ..delivery_outcome import DELIVERY_OUTCOME_CHOICES
from ..global_registry import sync_project_registry_to_global
from ..history import append_benchmark_run, render_benchmark_run_append_markdown
from ..status import compact_benchmark_run


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]

AGENTISSUE_RUNNER_FLOW_COMMANDS = {"agentissue-codex-runner-flow"}


def register_agentissue_runner_flow_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    agentissue_runner_flow_parser = benchmark_subparsers.add_parser(
        "agentissue-codex-runner-flow",
        help=(
            "Render or append the AgentIssue-Bench lagent_239 Codex CLI runner "
            "dry-run wrapper. No Codex, Docker, model API, upload, or submit is run."
        ),
    )
    add_subcommand_format(agentissue_runner_flow_parser)
    agentissue_runner_flow_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal id for dry-run/append context.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--tag",
        default=AGENTISSUE_DEFAULT_TAG,
        help="Selected public AgentIssue-Bench tag. Currently only lagent_239 is supported.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="Public command label for host-local Codex CLI command rendering.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--docker-binary",
        default="docker",
        help="Public command label for selected-tag Docker eval command rendering.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--synthetic-staging-root",
        help=(
            "Materialize a synthetic private job root at PATH with placeholder "
            "prompt, patch-output parent, and compact reducer files. Still no "
            "Codex, Docker, model API, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--execution-gate-root",
        help=(
            "Materialize a guarded no-execute real-source/host-Codex gate at "
            "PATH. It renders selected-container source extraction, private git "
            "baseline, host Codex, patch export, and eval command shapes without "
            "running Codex, Docker, model APIs, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--first-run-handoff-root",
        help=(
            "Materialize a no-execute first-run handoff packet at PATH. It "
            "includes the execution gate plus public handoff JSON/Markdown with "
            "command shape, private artifact boundary, compact outputs, and "
            "budget/auth safety checks."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--workflow-check-root",
        help=(
            "Materialize a no-execute workflow invariant check packet at PATH. "
            "It includes the first-run handoff plus workflow-check.public.json "
            "for phase, auth, artifact, and stop-rule checks without running "
            "Codex, Docker, model APIs, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--run-gate-root",
        help=(
            "Materialize a no-execute run-specific gate packet at PATH. It "
            "includes the workflow check plus run-specific owner/agent gates "
            "for a later no-upload lagent_239 run without running Codex, Docker, "
            "model APIs, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--target-runner-handoff-root",
        help=(
            "Materialize a no-execute target-runner handoff packet at PATH. It "
            "includes the run-specific gate plus a compact checklist for a "
            "separate benchmark execution thread without running Codex, Docker, "
            "model APIs, upload, submit, ranking paths, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--real-result-root",
        help=(
            "Reduce an already completed private real run from "
            "benchmark_run.compact.json and benchmark_result.compact.json at "
            "PATH. Reads compact files only; no Codex, Docker, model API, raw "
            "artifact, upload, submit, or public ranking path is invoked."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--private-runner-root",
        help=(
            "Materialize a private runnable lagent_239 script plus public "
            "manifest at PATH. The generator itself invokes no Codex, Docker, "
            "model API, upload, submit, or public ranking path; the script is "
            "for a later trusted local execution."
        ),
    )
    agentissue_runner_flow_parser.add_argument("--classification")
    agentissue_runner_flow_parser.add_argument("--recommended-action")
    agentissue_runner_flow_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional delivery scale label for the run index.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional delivery outcome label for the run index.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview append without writing. This is the default.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--execute",
        action="store_true",
        help="Append the selected compact runner-flow event.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Skip global registry sync after append.",
    )


def _default_classification(args: argparse.Namespace) -> str:
    if args.classification:
        return str(args.classification)
    if args.private_runner_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION
    if args.real_result_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION
    if args.target_runner_handoff_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION
    if args.run_gate_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION
    if args.workflow_check_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION
    if args.first_run_handoff_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION
    if args.execution_gate_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION
    if args.synthetic_staging_root:
        return AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION
    return AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION


def _recommended_next_action(
    *,
    args: argparse.Namespace,
    private_runner_script: dict[str, object] | None,
    real_result: dict[str, object] | None,
    target_handoff: dict[str, object] | None,
    run_gate: dict[str, object] | None,
    workflow_check: dict[str, object] | None,
    first_run_handoff: dict[str, object] | None,
    execution_gate: dict[str, object] | None,
    synthetic_staging: dict[str, object] | None,
    wrapper: dict[str, object],
) -> object:
    if args.recommended_action:
        return args.recommended_action
    for payload in (
        private_runner_script,
        real_result,
        target_handoff,
        run_gate,
        workflow_check,
        first_run_handoff,
        execution_gate,
        synthetic_staging,
        wrapper,
    ):
        if payload and "recommended_next_action" in payload:
            return payload["recommended_next_action"]
    return None


def handle_agentissue_runner_flow_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
) -> int | None:
    if args.benchmark_command not in AGENTISSUE_RUNNER_FLOW_COMMANDS:
        return None

    classification = _default_classification(args)
    try:
        if args.dry_run and args.execute:
            raise ValueError(
                "agentissue-codex-runner-flow accepts either --dry-run or --execute, not both"
            )
        selected_roots = [
            value
            for value in (
                args.synthetic_staging_root,
                args.execution_gate_root,
                args.first_run_handoff_root,
                args.workflow_check_root,
                args.run_gate_root,
                args.target_runner_handoff_root,
                args.real_result_root,
                args.private_runner_root,
            )
            if value
        ]
        if len(selected_roots) > 1:
            raise ValueError(
                "agentissue-codex-runner-flow accepts at most one root option, not both: --synthetic-staging-root, --execution-gate-root, --first-run-handoff-root, --workflow-check-root, --run-gate-root, --target-runner-handoff-root, --real-result-root, or --private-runner-root"
            )
        wrapper = build_agentissue_codex_cli_runner_wrapper(
            selected_tag=args.tag,
            codex_binary=args.codex_binary,
            docker_binary=args.docker_binary,
        )
        synthetic_staging = None
        execution_gate = None
        first_run_handoff = None
        workflow_check = None
        run_gate = None
        target_handoff = None
        real_result = None
        private_runner_script = None
        benchmark_run_source = wrapper["benchmark_run"]
        if args.private_runner_root:
            private_runner_script = (
                materialize_agentissue_codex_cli_runner_private_script(
                    args.private_runner_root,
                    selected_tag=args.tag,
                    codex_binary=args.codex_binary,
                    docker_binary=args.docker_binary,
                )
            )
            benchmark_run_source = private_runner_script["benchmark_run"]
        elif args.real_result_root:
            real_result = materialize_agentissue_codex_cli_runner_real_result(
                args.real_result_root,
                selected_tag=args.tag,
            )
            benchmark_run_source = real_result["benchmark_run"]
        elif args.target_runner_handoff_root:
            target_handoff = materialize_agentissue_codex_cli_runner_target_handoff(
                args.target_runner_handoff_root,
                selected_tag=args.tag,
                codex_binary=args.codex_binary,
                docker_binary=args.docker_binary,
            )
            benchmark_run_source = target_handoff["benchmark_run"]
        elif args.run_gate_root:
            run_gate = materialize_agentissue_codex_cli_runner_run_gate(
                args.run_gate_root,
                selected_tag=args.tag,
                codex_binary=args.codex_binary,
                docker_binary=args.docker_binary,
            )
            benchmark_run_source = run_gate["benchmark_run"]
        elif args.workflow_check_root:
            workflow_check = materialize_agentissue_codex_cli_runner_workflow_check(
                args.workflow_check_root,
                selected_tag=args.tag,
                codex_binary=args.codex_binary,
                docker_binary=args.docker_binary,
            )
            benchmark_run_source = workflow_check["benchmark_run"]
        elif args.first_run_handoff_root:
            first_run_handoff = (
                materialize_agentissue_codex_cli_runner_first_run_handoff(
                    args.first_run_handoff_root,
                    selected_tag=args.tag,
                    codex_binary=args.codex_binary,
                    docker_binary=args.docker_binary,
                )
            )
            benchmark_run_source = first_run_handoff["benchmark_run"]
        elif args.execution_gate_root:
            execution_gate = materialize_agentissue_codex_cli_runner_execution_gate(
                args.execution_gate_root,
                selected_tag=args.tag,
                codex_binary=args.codex_binary,
                docker_binary=args.docker_binary,
            )
            benchmark_run_source = execution_gate["benchmark_run"]
        elif args.synthetic_staging_root:
            synthetic_staging = (
                materialize_agentissue_codex_cli_runner_synthetic_staging(
                    args.synthetic_staging_root,
                    selected_tag=args.tag,
                    codex_binary=args.codex_binary,
                    docker_binary=args.docker_binary,
                )
            )
            benchmark_run_source = synthetic_staging["benchmark_run"]
        benchmark_run = compact_benchmark_run(benchmark_run_source)
        if not benchmark_run:
            raise ValueError(
                "agentissue Codex runner wrapper did not produce a compactable benchmark_run_v0"
            )
        dry_run = not bool(args.execute)
        payload = append_benchmark_run(
            registry_path=registry_path,
            runtime_root_override=args.runtime_root,
            goal_id=args.goal_id,
            benchmark_run=benchmark_run,
            classification=classification,
            recommended_action=_recommended_next_action(
                args=args,
                private_runner_script=private_runner_script,
                real_result=real_result,
                target_handoff=target_handoff,
                run_gate=run_gate,
                workflow_check=workflow_check,
                first_run_handoff=first_run_handoff,
                execution_gate=execution_gate,
                synthetic_staging=synthetic_staging,
                wrapper=wrapper,
            ),
            delivery_batch_scale=args.delivery_batch_scale,
            delivery_outcome=args.delivery_outcome,
            dry_run=dry_run,
        )
        payload["benchmark_cli"] = {
            "benchmark": AGENTISSUE_BENCHMARK_ID,
            "command": "agentissue-codex-runner-flow",
            "tag": args.tag,
            "dry_run_default": True,
            "real_runner_invoked": False,
            "real_codex_invoked": False,
            "real_docker_invoked": False,
            "model_api_invoked": False,
            "auth_values_read": False,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "synthetic_staging_materialized": bool(synthetic_staging),
            "synthetic_staging_root_path_recorded": False,
            "execution_gate_materialized": bool(execution_gate),
            "execution_gate_root_path_recorded": False,
            "first_run_handoff_materialized": bool(first_run_handoff),
            "first_run_handoff_root_path_recorded": False,
            "workflow_check_materialized": bool(workflow_check),
            "workflow_check_root_path_recorded": False,
            "run_gate_materialized": bool(run_gate),
            "run_gate_root_path_recorded": False,
            "target_handoff_materialized": bool(target_handoff),
            "target_handoff_root_path_recorded": False,
            "real_result_materialized": bool(real_result),
            "real_result_root_path_recorded": False,
            "real_result_read_boundary": "compact_only" if real_result else None,
            "private_runner_script_materialized": bool(private_runner_script),
            "private_runner_root_path_recorded": False,
            "private_runner_script_content_public": False,
        }
        payload["agentissue_runner_flow"] = wrapper
        if synthetic_staging:
            payload["agentissue_synthetic_staging"] = synthetic_staging
        if execution_gate:
            payload["agentissue_execution_gate"] = execution_gate
        if first_run_handoff:
            payload["agentissue_first_run_handoff"] = first_run_handoff
        if workflow_check:
            payload["agentissue_workflow_check"] = workflow_check
        if run_gate:
            payload["agentissue_run_gate"] = run_gate
        if target_handoff:
            payload["agentissue_target_handoff"] = target_handoff
        if real_result:
            payload["agentissue_real_result"] = real_result
            payload["benchmark_result"] = real_result["benchmark_result"]
        if private_runner_script:
            payload["agentissue_private_runner_script"] = private_runner_script
        if args.no_global_sync:
            payload["global_sync"] = {
                "ok": True,
                "dry_run": dry_run,
                "skipped": True,
                "reason": "disabled by --no-global-sync",
            }
        else:
            payload["global_sync"] = sync_project_registry_to_global(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                dry_run=dry_run,
            )
    except Exception as exc:
        payload = {
            "ok": False,
            "dry_run": not bool(getattr(args, "execute", False)),
            "appended": False,
            "registry": str(registry_path),
            "runtime_root": args.runtime_root,
            "goal_id": args.goal_id,
            "classification": classification,
            "error": str(exc),
        }
    print_payload(payload, args.format, render_benchmark_run_append_markdown)
    return 0 if payload.get("ok") else 1
