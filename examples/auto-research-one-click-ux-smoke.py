#!/usr/bin/env python3
"""Smoke-test the one-command visible auto-research UX."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE = REPO_ROOT / "docs" / "guides" / "auto-research-command-path.md"
GOAL_ID = "loopx-auto-research-knn"
TRACKING_GOAL_ID = "loopx-meta"
AGENT_ID = "codex-side-bypass"
SESSION = "loopx-auto-research-one-click-smoke"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        tmux_log = temp / "tmux.jsonl"
        workspace = temp / "one-click-workspace"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        write_executable(fake_bin / "loopx", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(fake_bin / "codex", "#!/usr/bin/env sh\nexit 0\n")
        write_executable(
            fake_bin / "tmux",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "lanes = ['frontier', 'research-curator', 'hypothesis-mapper', 'evidence-runner']",
                    "with open(os.environ['FAKE_TMUX_LOG'], 'a', encoding='utf-8') as f:",
                    "    f.write(json.dumps(sys.argv[1:]) + '\\n')",
                    "if len(sys.argv) > 1 and sys.argv[1] == 'has-session':",
                    "    raise SystemExit(1)",
                    "if len(sys.argv) > 1 and sys.argv[1] == 'list-windows':",
                    "    print('\\n'.join(lanes))",
                    "    raise SystemExit(0)",
                    "if len(sys.argv) > 1 and sys.argv[1] == 'capture-pane':",
                    "    print('[LoopX visible acceptance]')",
                    "    print('[LoopX role profile]')",
                    "    print('role_profile=printed')",
                    "    print('[LoopX quota guard]')",
                    "    print('quota_guard=printed')",
                    "    print('[LoopX auto-research frontier]')",
                    "    print('frontier_or_blocked_reason=printed')",
                    "    print('[bootstrap-or-stop]')",
                    "    print('bootstrap_or_stop=printed')",
                    "    print('worker_skill_path=.codex/skills/loopx-auto-research/SKILL.md')",
                    "    print('loopx_agent_handshake=role_profile_quota_frontier_bootstrap')",
                    "    raise SystemExit(0)",
                    "raise SystemExit(0)",
                    "",
                ]
            ),
        )

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["FAKE_TMUX_LOG"] = str(tmux_log)

        supervisor = subprocess.run(
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
                "demo-supervisor",
                "--goal-id",
                GOAL_ID,
                "--reasoning-effort",
                "high",
            ],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        supervisor_payload = json.loads(supervisor.stdout)
        assert supervisor_payload["ok"] is True, supervisor_payload
        assert supervisor_payload["reasoning_contract"]["default_reasoning_effort"] == "high", supervisor_payload
        for lane in supervisor_payload["lanes"]:
            bootstrap = lane["bootstrap_message"]
            launch_command = lane["visible_launch_command"]
            assert "codex-cli-bootstrap-message" not in bootstrap, lane
            assert "generic LoopX heartbeat worker" in bootstrap, lane
            assert "loopx-auto-research" in bootstrap, lane
            assert "Minimal live worker-turn path" in bootstrap, lane
            assert "auto-research worker-turn" in bootstrap, lane
            assert "--complete-selected-todo" in bootstrap, lane
            assert "$LOOPX_PANE_LOOPX" in bootstrap, lane
            assert "append-result.public.json" in bootstrap, lane
            assert "capture-live-evidence" in bootstrap, lane
            assert "live-codex-e2e-evidence.public.json" in bootstrap, lane
            assert "lightweight multi-round kernel is not live Codex evidence" in bootstrap, lane
            assert "claim_allowed must remain false" in bootstrap, lane
            assert "model_reasoning_effort=high" in bootstrap, lane
            assert "model_reasoning_effort=high" in launch_command, lane
            assert "codex-cli-bootstrap-message" not in launch_command, lane
        assert_public_safe(supervisor_payload)

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
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--tracking-goal-id",
                TRACKING_GOAL_ID,
                "--reasoning-effort",
                "high",
                "--execute",
                "--launch-visible",
                "--launcher",
                "tmux",
                "--session-name",
                SESSION,
                "--workspace",
                str(workspace),
                "--create-workspace",
            ],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["mode"] == "execute", payload
        assert payload["goal_id"] == GOAL_ID, payload
        assert payload["tracking_goal_id"] == TRACKING_GOAL_ID, payload
        route = payload["route_contract"]
        assert route["frontier_goal_id"] == GOAL_ID, payload
        assert route["visible_lanes_read_goal_id"] == GOAL_ID, payload
        assert route["tracking_goal_id"] == TRACKING_GOAL_ID, payload
        assert route["tracking_goal_drives_frontier"] is False, payload
        assert route["dedicated_positive_demo_frontier"] is True, payload
        assert payload["execution_kind"] == "minimal_research_kernel", payload
        assert payload["result_source"] == "deterministic_protected_eval_kernel", payload
        assert payload["reasoning_effort"] == "high", payload
        assert payload["research_loop"]["dev_round_count"] == 2, payload
        assert payload["research_loop"]["evidence_event_count"] == 3, payload
        assert payload["research_loop"]["live_codex_lane_authored"] is False, payload
        assert len(payload["research_loop"]["kernel_event_trace"]) == 3, payload
        assert payload["research_loop"]["dev_gain_over_baseline"] == 3.0, payload
        assert payload["research_loop"]["holdout_gain_over_baseline"] == 3.5, payload
        gain_acceptance = payload["multiround_gain_acceptance"]
        assert gain_acceptance["round_count"] == 2, payload
        assert gain_acceptance["hypotheses_attempted"] == [
            "hyp_full_sort",
            "hyp_partial_selection",
        ], payload
        assert gain_acceptance["evidence_events_appended"] == 3, payload
        assert gain_acceptance["final_gain_over_seed"] == 3.5, payload
        assert gain_acceptance["better_than_seed"] is True, payload
        assert "partial-selection hypothesis beats the seed" in gain_acceptance["why_better"], payload
        assert gain_acceptance["live_codex_lane_authored"] is False, payload
        assert payload["protected_eval_result"]["dev_metric"] == 4.0, payload
        assert payload["protected_eval_result"]["holdout_metric"] == 4.5, payload
        assert (
            payload["protected_eval_result"]["result_source"]
            == "generated_quickstart_pack_protected_eval"
        ), payload
        assert payload["protected_eval_result"]["protected_scope_clean"] is True, payload
        assert payload["acceptance"]["ready_for_real_launch"] is True, payload
        assert payload["public_boundary"]["launches_visible_lanes"] is True, payload
        assert payload["public_boundary"]["local_workspace_path_redacted"] is True, payload
        assert payload["public_boundary"]["live_codex_sessions_recorded"] is False, payload
        live = payload["live_codex_e2e"]
        assert live["executed"] is False, payload
        assert live["claim_allowed"] is False, payload
        assert live["visible_lanes_launched"] is True, payload
        assert live["evidence_source"] == "not_collected_from_codex_lane_output", payload
        visible = payload["visible_launch"]
        assert visible["mode"] == "executed_visible_launch", visible
        assert visible["boundary"]["shared_goal_surface"] is True, visible
        assert visible["boundary"]["all_lane_workspace_isolation"] is False, visible
        launch = visible["launch_result"]
        assert launch["launcher"] == "tmux", launch
        assert launch["session_name"] == SESSION, launch
        assert launch["workspace_mode"] == "explicit_workspace", launch
        assert launch["started_lane_count"] == 3, launch
        worker_skills = launch["worker_skill_materialization"]
        assert len(worker_skills) == 3, launch
        assert all(item["skill"] == "loopx-auto-research" for item in worker_skills), launch
        assert all(item["materialized"] for item in worker_skills), launch
        assert all(not item.get("missing_source") for item in worker_skills), launch
        assert all(
            item["destination"] == ".codex/skills/loopx-auto-research/SKILL.md"
            for item in worker_skills
        ), launch
        worker_skill_path = workspace / ".codex/skills/loopx-auto-research/SKILL.md"
        worker_skill_text = worker_skill_path.read_text(encoding="utf-8")
        assert "name: loopx-auto-research" in worker_skill_text, worker_skill_text
        assert "worker-local role playbook" in worker_skill_text, worker_skill_text
        assert launch["visible_acceptance"]["accepted"] is True, launch
        assert payload["live_codex_e2e"]["visible_lanes_accepted"] is True, payload
        assert workspace.is_dir(), workspace

        guide = GUIDE.read_text(encoding="utf-8")
        normalized_guide = " ".join(guide.split())
        one_command_section = guide.split("To run the multi-round path and open visible panes", 1)[1].split(
            "If you want to inspect before opening visible Codex lanes",
            1,
        )[0]
        for snippet in [
            "auto-research demo-e2e",
            "--execute",
            "--launch-visible",
            "--launcher tmux",
            "--workspace ./loopx-auto-research-demo",
            "--create-workspace",
            "--attach",
            "Generic\nlauncher internals stay inside LoopX",
            "multi-round visible demo",
        ]:
            assert snippet in one_command_section, snippet
        assert "does not claim that visible Codex lanes authored the research result" in normalized_guide, guide
        assert "live_codex_e2e.claim_allowed" in guide, guide
        assert "visible_multi_agent_launcher" not in guide, guide
        assert "loopx/visible_multi_agent_launcher.py" not in guide, guide
        assert_public_safe(one_command_section)
        assert_public_safe(payload)

        log_entries = [json.loads(line) for line in tmux_log.read_text(encoding="utf-8").splitlines()]
        assert any(entry[:1] == ["new-session"] for entry in log_entries), log_entries
        assert sum(1 for entry in log_entries if entry[:1] == ["new-window"]) == 3, log_entries
        script_paths = [
            Path(entry[-1])
            for entry in log_entries
            if entry[:1] in (["new-session"], ["new-window"])
        ]
        assert len(script_paths) == 4, log_entries
        script_text = "\n".join(path.read_text(encoding="utf-8") for path in script_paths)
        assert f"--goal-id {GOAL_ID}" in script_text, script_text
        assert f"--goal-id {TRACKING_GOAL_ID}" not in script_text, script_text
        assert "LOOPX_VISIBLE_LANE_COUNT=3" in script_text, script_text
        assert "LOOPX_REQUIRED_SKILL=loopx-auto-research" in script_text, script_text
        assert "LOOPX_ROLE_PROFILE_PATH" in script_text, script_text
        assert "role_profile_path=%s" in script_text, script_text
        assert "LOOPX_WORKER_SKILL_PATH" in script_text, script_text
        assert "worker_skill_path=%s" in script_text, script_text
        assert "model_reasoning_effort=high" in script_text, script_text
        assert "append-result.public.json" in script_text, script_text
        assert "capture-live-evidence" in script_text, script_text
        assert any(entry[:1] == ["list-windows"] for entry in log_entries), log_entries
        assert sum(1 for entry in log_entries if entry[:1] == ["capture-pane"]) == 3, log_entries

    print("auto-research-one-click-ux-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
