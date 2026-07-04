#!/usr/bin/env python3
"""Smoke-test the one-command demo-e2e path with a real LoopX worker loop."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_ID = "auto-research-operator"
GOAL_ID = "loopx-auto-research-demo-worker-loop-smoke"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.capabilities.auto_research.demo_e2e import run_auto_research_demo_e2e
    from loopx.capabilities.auto_research.human_view import render_auto_research_markdown
    from loopx.capabilities.auto_research.preset import (
        auto_research_role_id,
        default_auto_research_agent_specs,
    )

    launcher_source = (REPO_ROOT / "loopx/visible_multi_agent_launcher.py").read_text(
        encoding="utf-8"
    )
    runtime_scripts_source = (
        REPO_ROOT / "loopx/capabilities/multi_agent/runtime_scripts.py"
    ).read_text(encoding="utf-8")
    demo_e2e_source = (
        REPO_ROOT / "loopx/capabilities/auto_research/demo_e2e.py"
    ).read_text(encoding="utf-8")
    preset_source = (
        REPO_ROOT / "loopx/capabilities/auto_research/preset.py"
    ).read_text(encoding="utf-8")
    assert "raw JSON is not printed in visible panes" in runtime_scripts_source
    assert "Use $LOOPX_PANE_LOOPX for human-readable output" in runtime_scripts_source
    assert "$LOOPX_PANE_LOOPX_JSON <command>" in runtime_scripts_source
    assert "$LOOPX_PANE_ARTIFACT_DIR/<name>.public.json" in runtime_scripts_source
    assert "It injects --format json unless you pass an explicit --format." in runtime_scripts_source
    assert "$LOOPX_PANE_LOOPX_JSON is a command path, not an output file." in runtime_scripts_source
    assert "LOOPX_PANE_WORKER_TURN" in launcher_source
    assert "loopx-pane-a2a-tick" in runtime_scripts_source
    assert "role_prompt_public_artifact_for_first_turn_and_fixed_wake" in launcher_source
    assert "model_reasoning_effort" in launcher_source
    assert "codex_stream_filter" not in launcher_source
    assert "build_auto_research_quickstart" not in demo_e2e_source
    assert "quickstart_preview" not in demo_e2e_source
    assert "DEFAULT_WORKER_LOOP_AGENT_SPECS" not in demo_e2e_source
    assert "title_by_action" not in demo_e2e_source
    assert "AUTO_RESEARCH_DEFAULT_LANES" in preset_source
    assert "AUTO_RESEARCH_SEED_TITLES" in preset_source
    assert "codex-product-capability" not in preset_source
    assert "codex-side-bypass" not in preset_source
    assert "codex-main-control" not in preset_source
    assert "codex-value-explorer" not in preset_source
    assert default_auto_research_agent_specs() == [
        "research-curator:research-curator:research_curator",
        "hypothesis-proposer:hypothesis-proposer:hypothesis_proposer",
        "research-executor:research-executor:research_executor",
        "evaluator-promoter:evaluator-promoter:evaluator_promoter",
    ]
    for legacy_agent_id in (
        "codex-product-capability",
        "codex-side-bypass",
        "codex-main-control",
        "codex-value-explorer",
    ):
        try:
            auto_research_role_id(legacy_agent_id, index=1)
        except ValueError as exc:
            assert "unknown auto-research role_id" in str(exc), exc
        else:
            raise AssertionError(f"legacy agent id accepted as auto-research role: {legacy_agent_id}")

    worker_markdown = render_auto_research_markdown(
        {
            "ok": True,
            "schema_version": "auto_research_worker_turn_v0",
            "mode": "dry_run",
            "goal_id": GOAL_ID,
            "agent_id": AGENT_ID,
            "selected_todo_id": "todo_worker_smoke",
            "selected_action": "run_dev_eval",
            "would_execute": "run_dev_eval",
            "executed": False,
            "completion": {"requested": False, "executed": False},
            "frontier": {
                "quota": {
                    "should_run": True,
                    "state": "eligible",
                    "user_action_required": False,
                },
                "frontier": {
                    "selected": {
                        "todo_id": "todo_worker_smoke",
                        "allowed_action": "run_dev_eval",
                        "title": "Run dev evidence.",
                    }
                },
            },
        }
    )
    assert "# LoopX Auto Research Worker Turn" in worker_markdown
    assert "- selected_action: `run_dev_eval`" in worker_markdown
    assert '"schema_version"' not in worker_markdown

    blocked_markdown = render_auto_research_markdown(
        {
            "ok": True,
            "schema_version": "auto_research_worker_turn_v0",
            "mode": "blocked",
            "goal_id": GOAL_ID,
            "agent_id": "evaluator-promoter",
            "selected_todo_id": "todo_holdout_smoke",
            "selected_action": "run_holdout_eval",
            "executed": False,
            "blocker": "waiting_for_dev_evidence",
            "blocker_detail": "no dev-supported auto-research hypothesis is ready for holdout validation",
            "completion": {"requested": True, "executed": False},
            "frontier": {
                "quota": {
                    "should_run": True,
                    "state": "eligible",
                    "user_action_required": False,
                },
                "frontier": {
                    "selected": {
                        "todo_id": "todo_holdout_smoke",
                        "allowed_action": "run_holdout_eval",
                        "title": "Run held-out validation.",
                    }
                },
            },
        }
    )
    assert "- mode: `blocked`" in blocked_markdown
    assert "- blocker: `waiting_for_dev_evidence`" in blocked_markdown
    assert "Traceback" not in blocked_markdown

    with tempfile.TemporaryDirectory(prefix="loopx-visible-live-evidence-smoke.") as tmp:
        tmp_root = Path(tmp)
        session_name = "loopx-visible-live-evidence-smoke"

        def visible_launcher(
            _supervisor: dict[str, object],
            _visible_registry_path: Path,
            visible_runtime_root_arg: str | None,
            _default_workspace: Path,
        ) -> dict[str, object]:
            assert visible_runtime_root_arg
            artifact_dir = (
                Path(visible_runtime_root_arg)
                / "visible-launcher-artifacts"
                / session_name
                / "research_executor"
            )
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "pane-a2a-rounds.public.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "schema_version": "pane_local_a2a_tick_rounds_v0",
                        "source": "pane_local_a2a_tick",
                        "goal_id": GOAL_ID,
                        "agent_id": "research-executor",
                        "role_id": "research_executor",
                        "coordination_model": "decentralized_state_a2a",
                        "workflow_driver": False,
                        "status": "completed",
                        "rounds_requested": 4,
                        "rounds_completed": 4,
                        "worker_label": "worker-turn",
                        "worker_configured": True,
                        "rounds": [
                            {
                                "round_index": round_index,
                                "quota_status": 0,
                                "worker_configured": True,
                                "worker_executed": True,
                                "worker_status": 0,
                            }
                            for round_index in range(1, 5)
                        ],
                        "public_boundary": {
                            "raw_logs_recorded": False,
                            "private_artifacts_recorded": False,
                            "absolute_paths_recorded": False,
                            "credentials_recorded": False,
                            "local_workspace_path_redacted": True,
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (artifact_dir / "live-codex-e2e-evidence.public.json").write_text(
                json.dumps(
                    {
                        "schema_version": "auto_research_live_codex_lane_e2e_evidence_v0",
                        "source": "live_codex_lane_output",
                        "goal_id": GOAL_ID,
                        "agent_id": "research-executor",
                        "visible_lanes": {
                            "launched": True,
                            "accepted": True,
                            "lane_count": 1,
                        },
                        "lane_evidence": {
                            "append_status": "appended_to_loopx_state",
                            "dev_metric": 4.0,
                            "holdout_metric": 4.5,
                            "evidence_event_count": 2,
                            "evidence_source": "live_codex_lane_output",
                            "lane_authored": True,
                            "protected_scope_clean": True,
                            "result_status": "supported",
                        },
                        "public_boundary": {
                            "raw_logs_recorded": False,
                            "private_artifacts_recorded": False,
                            "absolute_paths_recorded": False,
                            "credentials_recorded": False,
                            "local_workspace_path_redacted": True,
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            return {
                "mode": "executed_visible_launch",
                "launch_result": {
                    "session_name": session_name,
                    "visible_acceptance": {"accepted": True},
                },
                "boundary": {"reads_raw_transcripts": False},
            }

        def visible_wake(session: str, lanes: list[str]) -> dict[str, object]:
            assert session == session_name, session
            assert lanes == [], lanes
            target_lanes = lanes or ["<all-session-windows>"]
            return {
                "ok": True,
                "schema_version": "multi_agent_pane_a2a_wakeup_v0",
                "mode": "execute",
                "session_name": session,
                "target_lanes": target_lanes,
                "prompt": (
                    "LoopX pane-local A2A wakeup: read the pane-local role prompt, "
                    "then run $LOOPX_PANE_A2A_TICK for this visible research round."
                ),
                "prompt_hash": "wakehash",
                "coordination_model": "decentralized_state_a2a",
                "wakeup_model": "fixed_prompt_broadcast",
                "workflow_driver": False,
                "broadcaster_reads_frontier": False,
                "broadcaster_selects_todo": False,
                "pane_decision_owner": "codex_tui_agent_via_loopx_state",
                "pane_input_ready_verified": True,
                "pane_input_ready_checks": [
                    {
                        "lane": lane,
                        "ready": True,
                        "attempt_count": 1,
                        "capture_ok": True,
                        "ready_marker": "codex_tui_first_turn_ready",
                    }
                    for lane in target_lanes
                ],
                "prompt_submit_checks": [
                    {
                        "target": f"{session}:{lane}",
                        "initial_submit_key": "Enter",
                        "retry_submit_key": None,
                        "retry_count": 0,
                        "capture_ok": True,
                    }
                    for lane in target_lanes
                ],
                "prompt_delivery": "tmux_paste_buffer_after_codex_tui_first_turn_ready",
                "boundary": {
                    "writes_loopx_state": False,
                    "spends_loopx_quota": False,
                    "reads_raw_transcripts": False,
                    "reads_credentials": False,
                    "runs_worker_turn_directly": False,
                },
            }

        visible_loaded_payload = run_auto_research_demo_e2e(
            agent_id=AGENT_ID,
            goal_id=GOAL_ID,
            tracking_goal_id=None,
            objective="Smoke visible live evidence auto-load.",
            output_dir=str(tmp_root / "out"),
            execute=True,
            launch_visible=True,
            keep_workspace=False,
            registry_path=tmp_root / "registry.json",
            runtime_root_arg=str(tmp_root / "runtime"),
            session_name=session_name,
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="medium",
            output_language="en",
            live_evidence_path=None,
            append_evidence=lambda _path: {"ok": True},
            visible_launcher=visible_launcher,
            visible_wake=visible_wake,
            wake_visible_after_launch=True,
            visible_live_evidence_wait_seconds=0,
        )
        visible_loaded_proof = visible_loaded_payload["visible_worker_proof"]
        visible_loaded_evidence = visible_loaded_payload["live_worker_evidence"]
        visible_loaded_rounds = visible_loaded_payload["visible_pane_a2a_rounds"]
        visible_loaded_wake = visible_loaded_payload["visible_wake"]
        visible_loaded_readiness = visible_loaded_payload["visible_readiness"]
        assert visible_loaded_proof["lane_authored_evidence_loaded"] is True, visible_loaded_payload
        assert visible_loaded_proof["pane_local_a2a_rounds_loaded"] is True, visible_loaded_payload
        assert visible_loaded_proof["pane_local_a2a_round_count"] == 4, visible_loaded_payload
        assert visible_loaded_proof["pane_local_a2a_multi_tick_verified"] is True, visible_loaded_payload
        assert visible_loaded_proof["collective_research_rounds_loaded"] is True, visible_loaded_payload
        assert visible_loaded_proof["decentralized_a2a_rounds_verified"] is False, visible_loaded_payload
        assert visible_loaded_proof["cadence_wake_loaded"] is True, visible_loaded_payload
        assert visible_loaded_proof["cadence_wake_verified"] is True, visible_loaded_payload
        assert visible_loaded_proof["evidence_source"] == "visible_launcher_artifact", visible_loaded_payload
        assert visible_loaded_evidence["loaded"] is True, visible_loaded_payload
        assert visible_loaded_evidence["agent_id"] == "research-executor", visible_loaded_payload
        assert visible_loaded_evidence["dev_metric"] == 4.0, visible_loaded_payload
        assert visible_loaded_evidence["holdout_metric"] == 4.5, visible_loaded_payload
        assert visible_loaded_rounds["coordination_model"] == "decentralized_state_a2a", visible_loaded_rounds
        assert visible_loaded_rounds["workflow_driver"] is False, visible_loaded_rounds
        assert visible_loaded_rounds["round_unit"] == "pane_local_tick", visible_loaded_rounds
        assert visible_loaded_rounds["counts_as_collective_research_round"] is False, visible_loaded_rounds
        assert visible_loaded_rounds["max_rounds_completed"] == 4, visible_loaded_rounds
        assert visible_loaded_rounds["pane_local_multi_tick_verified"] is True, visible_loaded_rounds
        visible_loaded_collective = visible_loaded_payload["collective_research_rounds"]
        assert visible_loaded_collective["round_unit"] == "collective_agent_pass", visible_loaded_collective
        assert visible_loaded_collective["collective_round_count"] == 4, visible_loaded_collective
        assert visible_loaded_collective["full_participation_verified"] is False, visible_loaded_collective
        assert visible_loaded_collective["multi_round_research_verified"] is False, visible_loaded_collective
        assert visible_loaded_collective["full_participation_count_basis"] == (
            "synchronous_and_asynchronous"
        ), visible_loaded_collective
        assert visible_loaded_collective["full_participation_requirement_gap"][
            "shortfall_by_agent"
        ] == {
            "evaluator-promoter": 4,
            "hypothesis-proposer": 4,
            "research-curator": 4,
            "research-executor": 4,
        }, visible_loaded_collective
        assert visible_loaded_collective["holdout_improvement_count"] == 1, visible_loaded_collective
        assert visible_loaded_wake["wakeup_model"] == "fixed_prompt_broadcast", visible_loaded_wake
        assert visible_loaded_wake["coordination_model"] == "decentralized_state_a2a", visible_loaded_wake
        assert visible_loaded_wake["pane_input_ready_verified"] is True, visible_loaded_wake
        assert (
            visible_loaded_wake["prompt_delivery"]
            == "tmux_paste_buffer_after_codex_tui_first_turn_ready"
        ), visible_loaded_wake
        assert visible_loaded_wake["prompt_submit_checks"], visible_loaded_wake
        assert visible_loaded_wake["workflow_driver"] is False, visible_loaded_wake
        assert visible_loaded_wake["broadcaster_reads_frontier"] is False, visible_loaded_wake
        assert visible_loaded_wake["broadcaster_selects_todo"] is False, visible_loaded_wake
        assert visible_loaded_readiness["ready"] is False, visible_loaded_readiness
        assert visible_loaded_readiness["readiness_level"] == "collecting_evidence", visible_loaded_readiness
        assert visible_loaded_readiness["manual_artifact_inspection_required"] is True, visible_loaded_readiness
        assert visible_loaded_readiness["wake_model"] == "fixed_prompt_broadcast", visible_loaded_readiness
        assert visible_loaded_readiness["workflow_model"] == (
            "fixed_prompt_broadcast_plus_pane_local_state_tick"
        ), visible_loaded_readiness
        assert visible_loaded_readiness["driver_owner_layer"] == (
            "generic_multi_agent_kernel"
        ), visible_loaded_readiness
        assert visible_loaded_readiness["checks"]["kernel_driver_contract_loaded"] is True, visible_loaded_readiness
        assert visible_loaded_readiness["checks"]["workflow_driver_false"] is True, visible_loaded_readiness
        assert visible_loaded_readiness["checks"]["pane_local_tick_loaded"] is True, visible_loaded_readiness
        assert visible_loaded_readiness["checks"]["collective_research_multi_round_verified"] is False, visible_loaded_readiness
        assert visible_loaded_readiness["missing_requirements"] == [
            "collective_research_multi_round_verified"
        ], visible_loaded_readiness
        assert visible_loaded_readiness["rounds"]["counts_as_collective_research_round"] is False, visible_loaded_readiness
        assert visible_loaded_readiness["collective_research_rounds"]["count"] == 4, visible_loaded_readiness
        assert visible_loaded_readiness["collective_research_rounds"]["holdout_improvement_count"] == 1, visible_loaded_readiness
        assert visible_loaded_readiness["collective_research_rounds"][
            "full_participation_requirement_gap"
        ]["shortfall_by_agent"] == {
            "evaluator-promoter": 4,
            "hypothesis-proposer": 4,
            "research-curator": 4,
            "research-executor": 4,
        }, visible_loaded_readiness
        loaded_improvement = visible_loaded_readiness["improvement_summary"]
        assert loaded_improvement["baseline_metric"] == 1.0, loaded_improvement
        assert loaded_improvement["dev_metric_sequence"] == [4.0], loaded_improvement
        assert loaded_improvement["holdout_metric_sequence"] == [4.5], loaded_improvement
        assert loaded_improvement["final_dev_metric"] == 4.0, loaded_improvement
        assert loaded_improvement["final_holdout_metric"] == 4.5, loaded_improvement
        assert loaded_improvement["best_metric_source"] == "final_holdout", loaded_improvement
        assert loaded_improvement["holdout_delta_over_dev"] == 0.5, loaded_improvement
        assert visible_loaded_readiness["one_command"].endswith("--execute"), visible_loaded_readiness
        assert "--wake-visible-after-launch" not in visible_loaded_readiness["one_command"], visible_loaded_readiness
        visible_loaded_markdown = render_auto_research_markdown(visible_loaded_payload)
        assert "- visible_readiness_ready: `False`" in visible_loaded_markdown, visible_loaded_markdown
        assert "- visible_best_metric: `4.5`" in visible_loaded_markdown, visible_loaded_markdown
        assert_public_safe(visible_loaded_payload)

    loop_markdown = render_auto_research_markdown(
        {
            "ok": True,
            "schema_version": "auto_research_worker_loop_v0",
            "mode": "execute",
            "goal_id": GOAL_ID,
            "round_count": 1,
            "max_rounds": 4,
            "stop_reason": "no_runnable_frontier",
            "turn_count": 1,
            "executed_turn_count": 1,
            "completed_turn_count": 1,
            "selected_actions": ["run_dev_eval"],
            "turns": [
                {
                    "round": 1,
                    "agent_id": AGENT_ID,
                    "mode": "execute",
                    "selected_action": "run_dev_eval",
                    "executed": True,
                    "completion_status": "done",
                    "dev_metric": 4.0,
                    "holdout_metric": None,
                }
            ],
        }
    )
    assert "# LoopX Auto Research Worker Loop" in loop_markdown
    assert "agent `auto-research-operator`" in loop_markdown
    assert '"turns"' not in loop_markdown

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        workspace = temp / "workspace"
        workspace.mkdir()
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        fake_codex = fake_bin / "fake-codex-tui"
        fake_loopx = fake_bin / "loopx-under-test"
        codex_invocations = temp / "codex-invocations.txt"
        fake_codex.write_text(
            "#!/usr/bin/env sh\n"
            f"{{ printf 'PWD=%s\\n' \"$PWD\"; printf 'ARGS=%s\\n' \"$*\"; }} >> {shlex.quote(str(codex_invocations))}\n"
            "printf '╭────────────────────────╮\\n'\n"
            "printf '│ >_ OpenAI Codex        │\\n'\n"
            "printf '│ model: gpt-5.5 high    │\\n'\n"
            "printf '╰────────────────────────╯\\n\\n'\n"
            "printf '› Implement {feature}\\n'\n"
            "if [ -n \"${LOOPX_PANE_A2A_TICK:-}\" ] && [ -x \"$LOOPX_PANE_A2A_TICK\" ]; then\n"
            "  \"$LOOPX_PANE_A2A_TICK\" > \"${LOOPX_PANE_TICK_OUTPUT_ARTIFACT:-/dev/null}\" 2>&1\n"
            "  printf 'LoopX pane-local tick completed by visible Codex TUI.\\n'\n"
            "fi\n"
            "sleep 30\n",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        fake_loopx.write_text(
            "#!/usr/bin/env sh\n"
            f"exec {shlex.quote(sys.executable)} -m loopx.cli \"$@\"\n",
            encoding="utf-8",
        )
        fake_loopx.chmod(0o755)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["FAKE_TMUX_CAPTURE_TEXT"] = (
            "╭────────────────────────╮\n"
            "│ >_ OpenAI Codex        │\n"
            "│ model: gpt-5.5 high    │\n"
            "╰────────────────────────╯\n\n"
            "› Implement {feature}\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "auto-research",
                "demo-e2e",
                "--agent-id",
                AGENT_ID,
                "--demo-run-id",
                "worker-loop-smoke",
                "--execute",
                "--headless",
            ],
            cwd=workspace,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"demo-e2e worker-loop failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["goal_id"] == GOAL_ID, payload
        assert payload["execution_kind"] == "loopx_worker_loop", payload
        assert payload["result_source"] == "loopx_worker_loop_public_evidence", payload
        assert "protected_eval_result" not in payload, payload
        assert "research_loop" not in payload, payload
        assert "multiround_gain_acceptance" not in payload, payload
        assert payload["route_contract"]["goal_surface_mode"] == "fresh_demo_goal", payload
        supervisor = payload["supervisor"]
        assert supervisor["lane_count"] == 4, payload
        assert supervisor["uses_generic_runner"] is True, supervisor
        assert supervisor["generic_spec_schema"] == "generic_multi_agent_launch_spec_v0", supervisor
        assert supervisor["runner_contract_schema"] == "tui_multi_agent_runner_contract_v0", supervisor
        assert supervisor["machine_json_policy"] == "artifact_only_in_visible_panes", supervisor
        assert supervisor["domain_specific_runner_logic"] is False, supervisor
        assert supervisor["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", supervisor
        assert (
            supervisor["pane_local_a2a"]["machine_json_destination"]
            == "$LOOPX_PANE_ARTIFACT_DIR/*.public.json"
        ), supervisor
        assert (
            supervisor["kernel_boundary"]["coordination_pattern"]
            == "decentralized_state_a2a"
        ), supervisor
        assert supervisor["kernel_boundary"]["presentation_layers_in_kernel"] is False, supervisor
        worker_loop = payload["worker_loop"]
        assert worker_loop["schema_version"] == "auto_research_worker_loop_v0", payload
        assert worker_loop["mode"] == "execute", payload
        assert worker_loop["executed_turn_count"] == 16, payload
        assert worker_loop["completed_turn_count"] == 16, payload
        assert worker_loop["selected_actions"] == [
            "write_research_contract",
            "propose_hypothesis",
            "run_dev_eval",
            "summarize_evidence",
            "review_research_contract",
            "review_hypothesis_frontier",
            "run_holdout_eval",
            "write_evaluation_summary",
            "review_research_contract",
            "propose_hypothesis",
            "run_dev_eval",
            "review_promotion_readiness",
            "review_research_contract",
            "review_hypothesis_frontier",
            "run_holdout_eval",
            "write_evaluation_summary",
        ], payload
        assert all(turn["executed"] is True for turn in worker_loop["turns"]), worker_loop
        assert all(turn["completion_status"] == "done" for turn in worker_loop["turns"]), worker_loop
        assert worker_loop["stop_reason"] == "max_rounds", payload
        collective_rounds = payload["collective_research_rounds"]
        assert collective_rounds["round_unit"] == "collective_agent_pass", collective_rounds
        assert collective_rounds["collective_round_count"] == 4, collective_rounds
        assert collective_rounds["full_participation_round_count"] == 4, collective_rounds
        assert collective_rounds["full_participation_verified"] is True, collective_rounds
        assert collective_rounds["multi_round_research_verified"] is True, collective_rounds
        assert collective_rounds["dev_metric_sequence"] == [4.0, 4.8], collective_rounds
        assert collective_rounds["holdout_metric_sequence"] == [4.5, 5.2], collective_rounds
        assert collective_rounds["holdout_improvement_count"] == 2, collective_rounds
        assert collective_rounds["dev_metric"] == 4.8, collective_rounds
        assert collective_rounds["holdout_metric"] == 5.2, collective_rounds
        kernel_ledger = collective_rounds["kernel_ledger"]
        assert kernel_ledger["schema_version"] == "multi_agent_collective_round_ledger_v0"
        assert kernel_ledger["owner_layer"] == "generic_multi_agent_kernel", kernel_ledger
        assert kernel_ledger["expected_lane_count"] == 4, kernel_ledger
        assert kernel_ledger["collective_round_count"] == 4, kernel_ledger
        assert kernel_ledger["full_participation_round_count"] == 4, kernel_ledger
        assert kernel_ledger["full_participation_requirement_gap"]["shortfall_by_agent"] == {}, kernel_ledger
        assert kernel_ledger["full_participation_verified"] is True, kernel_ledger
        assert kernel_ledger["multi_round_interaction_verified"] is True, kernel_ledger
        assert kernel_ledger["successor_todo_count"] >= 1, kernel_ledger
        tonight = payload["tonight_experience"]
        assert tonight["ready"] is True, tonight
        assert tonight["positive_result"] is True, tonight
        assert tonight["positive_result_basis"] == "public_safe_dev_and_holdout_evidence", tonight
        assert tonight["coordination_pattern"] == "decentralized_state_a2a", tonight
        assert tonight["workflow_model"] == "state_projected_frontier_not_dynamic_workflow", tonight
        assert tonight["leader_agent_required"] is False, tonight
        assert tonight["dev_metric_sequence"] == [4.0, 4.8], tonight
        assert tonight["holdout_metric_sequence"] == [4.5, 5.2], tonight
        assert tonight["holdout_improvement_count"] == 2, tonight
        assert tonight["dev_metric"] == 4.8, tonight
        assert tonight["holdout_metric"] == 5.2, tonight
        assert "--run-worker-loop" in tonight["one_command"], tonight
        assert "--headless" not in tonight["one_command"], tonight
        assert "--headless" in payload["commands"]["headless_worker_loop"], payload
        assert "--no-attach" in payload["commands"]["start_visible_lanes_without_attach"], payload
        visible_proof = payload["visible_worker_proof"]
        assert visible_proof["schema_version"] == "auto_research_visible_worker_proof_v0", visible_proof
        assert visible_proof["owner_layer"] == "generic_multi_agent_kernel", visible_proof
        assert visible_proof["user_facing_by_default"] is False, visible_proof
        assert visible_proof["lane_authored_evidence_loaded"] is False, visible_proof
        assert visible_proof["visible_lanes_launched"] is False, visible_proof
        removed_replay_source = "deterministic_" + "protected_eval_kernel"
        assert removed_replay_source not in json.dumps(payload, sort_keys=True), payload
        assert_public_safe(payload)
        if shutil.which("tmux"):
            session_name = "loopx-auto-research-worker-skill-smoke"
            try:
                visible = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "loopx.cli",
                        "--registry",
                        str(registry),
                        "--runtime-root",
                        str(runtime_root),
                        "--format",
                        "json",
                        "auto-research",
                        "demo-e2e",
                        "--agent-id",
                        AGENT_ID,
                        "--demo-run-id",
                        "worker-skill-visible-smoke",
                        "--execute",
                        "--no-attach",
                        "--wake-visible-after-launch",
                        "--replace-existing",
                        "--session-name",
                        session_name,
                        "--codex-bin",
                        "fake-codex-tui",
                        "--cli-bin",
                        str(fake_loopx),
                        "--visible-live-evidence-wait-seconds",
                        "24",
                    ],
                    cwd=workspace,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if visible.returncode != 0:
                    raise AssertionError(
                        f"visible demo-e2e failed rc={visible.returncode}\nstdout={visible.stdout}\nstderr={visible.stderr}"
                    )
                visible_payload = json.loads(visible.stdout)
                assert visible_payload["execution_kind"] == "visible_worker_launch", visible_payload
                assert visible_payload["result_source"] == "visible_worker_launcher", visible_payload
                assert "worker_loop" not in visible_payload, visible_payload
                assert "tonight_experience" not in visible_payload, visible_payload
                assert "visible_readiness" in visible_payload, visible_payload
                visible_supervisor = visible_payload["supervisor"]
                assert visible_supervisor["uses_generic_runner"] is True, visible_supervisor
                assert visible_supervisor["machine_json_policy"] == "artifact_only_in_visible_panes", visible_supervisor
                assert (
                    visible_supervisor["pane_local_a2a"]["human_default"]
                    == "markdown_status_inside_codex_tui"
                ), visible_supervisor
                visible_driver = visible_supervisor["decentralized_a2a_driver"]
                assert visible_driver["owner_layer"] == "generic_multi_agent_kernel", visible_driver
                assert visible_driver["broadcaster_decides_work"] is False, visible_driver
                assert (
                    visible_driver["user_and_preset_do_not_own_tick_driver"] is True
                ), visible_driver
                visible_proof = visible_payload["visible_worker_proof"]
                assert visible_proof["schema_version"] == "auto_research_visible_worker_proof_v0", visible_proof
                assert visible_proof["owner_layer"] == "generic_multi_agent_kernel", visible_proof
                assert visible_proof["user_facing_by_default"] is False, visible_proof
                assert visible_proof["lane_authored_evidence_loaded"] is True, visible_proof
                assert visible_proof["evidence_source"] == "visible_launcher_artifact", visible_proof
                assert visible_proof["visible_lanes_launched"] is True, visible_proof
                assert visible_proof["pane_local_a2a_rounds_loaded"] is True, visible_proof
                assert visible_proof["pane_local_a2a_round_count"] >= 8, visible_proof
                assert visible_proof["pane_local_a2a_multi_tick_verified"] is True, visible_proof
                assert visible_proof["collective_research_rounds_loaded"] is True, visible_proof
                assert visible_proof["decentralized_a2a_rounds_verified"] is False, visible_proof
                assert visible_proof["collective_research_round_count"] >= 8, visible_proof
                assert visible_proof["holdout_improvement_count"] == 2, visible_proof
                assert visible_proof["cadence_wake_loaded"] is True, visible_proof
                assert visible_proof["cadence_wake_verified"] is True, visible_proof
                live_evidence = visible_payload.get("live_worker_evidence", {"loaded": False})
                assert live_evidence["loaded"] is True, live_evidence
                assert live_evidence["holdout_metric"] == 5.2, live_evidence
                visible_rounds = visible_payload["visible_pane_a2a_rounds"]
                assert visible_rounds["source"] == "visible_launcher_artifact", visible_rounds
                assert visible_rounds["coordination_model"] == "decentralized_state_a2a", visible_rounds
                assert visible_rounds["workflow_driver"] is False, visible_rounds
                assert visible_rounds["round_unit"] == "pane_local_tick", visible_rounds
                assert visible_rounds["counts_as_collective_research_round"] is False, visible_rounds
                assert visible_rounds["max_rounds_completed"] >= 2, visible_rounds
                assert visible_rounds["pane_local_multi_tick_verified"] is True, visible_rounds
                visible_wake = visible_payload["visible_wake"]
                assert visible_wake["schema_version"] == "multi_agent_pane_a2a_wakeup_v0", visible_wake
                assert visible_wake["mode"] == "execute", visible_wake
                assert visible_wake["target_lanes"] == [
                    "research-curator",
                    "hypothesis-proposer",
                    "research-executor",
                    "evaluator-promoter",
                ], visible_wake
                assert visible_wake["wakeup_model"] == "fixed_prompt_broadcast", visible_wake
                assert visible_wake["coordination_model"] == "decentralized_state_a2a", visible_wake
                assert visible_wake["driver_owner_layer"] == "generic_multi_agent_kernel", visible_wake
                assert visible_wake["workflow_driver"] is False, visible_wake
                assert visible_wake["broadcaster_reads_frontier"] is False, visible_wake
                assert visible_wake["broadcaster_selects_todo"] is False, visible_wake
                assert visible_wake["prompt_delivery"] in {
                    "tmux_paste_buffer_after_codex_tui_first_turn_ready",
                    "tmux_paste_buffer_after_ready_subset",
                    "skipped_no_input_ready_panes",
                }, visible_wake
                if visible_wake["pane_input_ready_verified"] is True:
                    assert visible_wake["prompt_submit_checks"], visible_wake
                    assert visible_wake["ready_lanes"], visible_wake
                    assert visible_wake["not_ready_lanes"] == [], visible_wake
                elif visible_wake["prompt_delivery"] == "tmux_paste_buffer_after_ready_subset":
                    assert visible_wake["prompt_submit_checks"], visible_wake
                    assert visible_wake["ready_lanes"], visible_wake
                    assert visible_wake["not_ready_lanes"], visible_wake
                else:
                    assert visible_wake["prompt_submit_checks"] == [], visible_wake
                    assert visible_wake["ready_lanes"] == [], visible_wake
                    assert visible_wake["not_ready_lanes"], visible_wake
                visible_readiness = visible_payload["visible_readiness"]
                assert visible_readiness["schema_version"] == "auto_research_visible_readiness_v0", visible_readiness
                assert visible_readiness["ready"] is False, visible_readiness
                assert visible_readiness["readiness_level"] == "collecting_evidence", visible_readiness
                assert visible_readiness["manual_artifact_inspection_required"] is True, visible_readiness
                assert visible_readiness["wake_model"] == "fixed_prompt_broadcast", visible_readiness
                assert visible_readiness["workflow_model"] == (
                    "fixed_prompt_broadcast_plus_pane_local_state_tick"
                ), visible_readiness
                assert visible_readiness["driver_owner_layer"] == (
                    "generic_multi_agent_kernel"
                ), visible_readiness
                assert visible_readiness["coordination_pattern"] == "decentralized_state_a2a", visible_readiness
                assert visible_readiness["leader_agent_required"] is False, visible_readiness
                assert visible_readiness["checks"] == {
                    "user_contract_accepted": True,
                    "visible_lanes_accepted": True,
                    "cadence_wake_verified": True,
                    "pane_local_tick_loaded": True,
                    "collective_research_multi_round_verified": False,
                    "lane_authored_evidence_loaded": True,
                    "protected_scope_clean": True,
                    "positive_metric_over_baseline": True,
                    "workflow_driver_false": True,
                    "kernel_driver_contract_loaded": True,
                }, visible_readiness
                assert visible_readiness["missing_requirements"] == [
                    "collective_research_multi_round_verified",
                ], visible_readiness
                assert visible_readiness["rounds"]["max_completed"] >= 8, visible_readiness
                assert visible_readiness["rounds"]["counts_as_collective_research_round"] is False, visible_readiness
                assert visible_readiness["collective_research_rounds"]["count"] >= 8, visible_readiness
                assert visible_readiness["collective_research_rounds"]["multi_round_verified"] is False, visible_readiness
                assert visible_readiness["collective_research_rounds"]["holdout_improvement_count"] == 2, visible_readiness
                visible_gap = visible_readiness["collective_research_rounds"][
                    "full_participation_requirement_gap"
                ]
                assert visible_gap["missing_agent_count"] >= 1, visible_readiness
                assert visible_gap["shortfall_by_agent"], visible_readiness
                improvement = visible_readiness["improvement_summary"]
                assert improvement["baseline_metric"] == 1.0, improvement
                assert improvement["dev_metric_sequence"] == [4.0, 4.8], improvement
                assert improvement["holdout_metric_sequence"] == [4.5, 5.2], improvement
                assert improvement["holdout_improvement_count"] == 2, improvement
                assert improvement["best_metric"] == 5.2, improvement
                assert improvement["best_metric_source"] == "final_holdout", improvement
                assert improvement["improved_over_baseline"] is True, improvement
                assert abs(improvement["holdout_delta_over_dev"] - 0.4) < 0.000001, improvement
                assert "auto-research start" in visible_readiness["one_command"], visible_readiness
                assert visible_readiness["one_command"].endswith("--execute"), visible_readiness
                assert "--wake-visible-after-launch" not in visible_readiness["one_command"], visible_readiness
                launch = visible_payload["visible_launch"]["launch_result"]
                assert launch["started_lane_count"] == 4, visible_payload
                assert "frontier" not in launch["started_lanes"], visible_payload
                assert launch["attach_requested"] is False, visible_payload
                assert launch["workspace_mode"] == "explicit_workspace", visible_payload
                assert launch["codex_trust_workspace"] is True, visible_payload
                assert (
                    launch["codex_trust_scope"] == "persisted_selected_workspace_and_git_root"
                ), visible_payload
                workspace_route = visible_payload["visible_control_plane"]["workspace_route"]
                assert workspace_route["side_lane_worktree_count"] == 0, workspace_route
                assert workspace_route["primary_workspace"] == "visible_codex_tui_workspace", workspace_route
                assert (
                    workspace_route["trust_prompt_avoidance"]
                    == "demo_owned_clean_workspace_with_persisted_codex_trust_config"
                ), workspace_route
                assert workspace_route["default_visible_workspace"] == "demo_owned_clean_workspace", workspace_route
                acceptance = launch["visible_acceptance"]
                assert acceptance["schema_version"] == "multi_agent_visible_launch_acceptance_v0", acceptance
                assert acceptance["accepted"] is True, visible_payload
                assert visible_proof["visible_lanes_accepted"] is True, visible_proof
                assert all(not item["blocked_before_bootstrap"] for item in acceptance["pane_checks"]), acceptance
                assert all(item["interactive_codex_tui_script"] for item in acceptance["pane_checks"]), acceptance
                skill_items = launch["worker_skill_materialization"]
                assert skill_items, visible_payload
                assert {item["source_resolution"] for item in skill_items} == {"package_root"}, skill_items
                assert all(item["materialized"] is True for item in skill_items), skill_items
                for _attempt in range(40):
                    if codex_invocations.exists() and codex_invocations.read_text(
                        encoding="utf-8"
                    ).count("PWD=") >= 4:
                        break
                    time.sleep(0.25)
                invocation_text = codex_invocations.read_text(encoding="utf-8")
                assert invocation_text.count("Fake Codex TUI") == 0, invocation_text
                assert invocation_text.count("PWD=") == 4, invocation_text
                assert invocation_text.count("visible-user-workspace") >= 8, invocation_text
                assert invocation_text.count("trust_level=trusted") == 0, invocation_text
                assert invocation_text.count('trust_level="trusted"') == 4, invocation_text
                assert "visible-lane-worktrees" not in invocation_text, invocation_text
                assert "visible-control-plane" not in invocation_text, invocation_text
                for lane in launch["started_lanes"]:
                    capture = subprocess.run(
                        ["tmux", "capture-pane", "-pt", f"{session_name}:{lane}", "-S", "-300"],
                        check=False,
                        capture_output=True,
                        text=True,
                    ).stdout
                    assert "state_projection_gap" not in capture, (lane, capture)
                    assert "stopped_before_frontier" not in capture, (lane, capture)
                    assert "quota_wait_timeout" not in capture, (lane, capture)
                    assert "frontier_wait_timeout" not in capture, (lane, capture)
                    assert '"schema_version"' not in capture, (lane, capture)
                    assert "LOOPX_ROLE_PROFILE_JSON" not in capture, (lane, capture)
                    assert "/" + "private/" not in capture, (lane, capture)
                    assert "/" + "tmp/" not in capture, (lane, capture)
                    assert "role_profile_path=" not in capture, (lane, capture)
                    assert "[Codex bootstrap prompt]" not in capture, (lane, capture)
                    assert "codex_output=streaming_below" not in capture, (lane, capture)
                    assert "codex_stream_filter=public_safe" not in capture, (lane, capture)
                assert_public_safe(visible_payload)
            finally:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
    print("auto-research-demo-e2e-worker-loop-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
