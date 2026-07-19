#!/usr/bin/env python3
"""Smoke-test readiness-targeted visible multi-agent wake scheduling."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.control_plane.agents.multi_agent.runtime_scripts import (  # noqa: E402
    CODEX_TUI_EXEC_PY,
)
from loopx.control_plane.agents.multi_agent.visible_wake_scheduler import (  # noqa: E402
    lane_agent_map,
    run_state_aware_wake_loop,
    todo_readiness_projection,
)


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def main() -> int:
    lanes = [
        {"lane_id": "curator", "agent_id": "research-curator"},
        {"lane_id": "proposer", "agent_id": "hypothesis-proposer"},
        {"lane_id": "fallback-agent"},
    ]
    agents = lane_agent_map(lanes)
    assert agents == {
        "curator": "research-curator",
        "proposer": "hypothesis-proposer",
        "fallback-agent": "fallback-agent",
    }, agents

    initial = todo_readiness_projection(
        {
            "todos": [
                {
                    "todo_id": "todo_curate",
                    "status": "open",
                    "done": False,
                    "claimed_by": "research-curator",
                },
                {
                    "todo_id": "todo_propose",
                    "status": "open",
                    "done": False,
                    "claimed_by": "hypothesis-proposer",
                    "resume_ready": False,
                },
            ]
        },
        lane_agents=agents,
    )
    assert initial["recognized"] is True, initial
    assert initial["goal_todo_count"] == 2, initial
    assert initial["mapped_todo_count"] == 2, initial
    assert initial["runnable_lane_tokens"] == {"curator": ("todo_curate",)}, initial

    successor = todo_readiness_projection(
        {
            "todos": [
                {
                    "todo_id": "todo_curate",
                    "status": "done",
                    "done": True,
                    "claimed_by": "research-curator",
                },
                {
                    "todo_id": "todo_propose_v2",
                    "status": "open",
                    "done": False,
                    "claimed_by": "hypothesis-proposer",
                    "resume_ready": True,
                },
            ]
        },
        lane_agents=agents,
    )
    assert successor["runnable_lane_tokens"] == {
        "proposer": ("todo_propose_v2",)
    }, successor

    unmapped = todo_readiness_projection(
        {"todos": [{"todo_id": "todo_other", "claimed_by": "other-agent"}]},
        lane_agents=agents,
    )
    assert unmapped["recognized"] is True, unmapped
    assert unmapped["runnable_lane_tokens"] == {}, unmapped

    unclaimed = todo_readiness_projection(
        {
            "todos": [
                {
                    "todo_id": "todo_unclaimed",
                    "status": "open",
                    "done": False,
                    "task_class": "advancement_task",
                    "excluded_agents": ["hypothesis-proposer"],
                }
            ]
        },
        lane_agents=agents,
    )
    assert unclaimed["runnable_lane_tokens"] == {
        "curator": ("todo_unclaimed",),
        "fallback-agent": ("todo_unclaimed",),
    }, unclaimed

    with tempfile.TemporaryDirectory(prefix="loopx-state-aware-wake-smoke.") as tmp:
        temp = Path(tmp)
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        state = temp / "todo-state.json"
        wake_log = temp / "wake-argv.json"
        stop = temp / "stop"
        artifact = temp / "auto-wake.public.jsonl"
        state.write_text(
            json.dumps(
                {
                    "todos": [
                        {
                            "todo_id": "todo_propose_v2",
                            "status": "open",
                            "done": False,
                            "claimed_by": "hypothesis-proposer",
                            "resume_ready": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        write_executable(
            fake_bin / "tmux",
            """#!/usr/bin/env python3
import os
import sys
raise SystemExit(1 if os.path.exists(os.environ['FAKE_STOP']) else 0)
""",
        )
        write_executable(
            fake_bin / "loopx",
            """#!/usr/bin/env python3
import json
import os
import sys
args = sys.argv[1:]
if 'todo' in args and 'list' in args:
    print(open(os.environ['FAKE_TODO_STATE'], encoding='utf-8').read())
    raise SystemExit(0)
if 'multi-agent' in args and 'wake' in args:
    with open(os.environ['FAKE_WAKE_LOG'], 'w', encoding='utf-8') as handle:
        json.dump(args, handle)
    open(os.environ['FAKE_STOP'], 'w', encoding='utf-8').write('stop')
    print(json.dumps({'ok': True, 'auto_wake_backoff_recommended': False}))
    raise SystemExit(0)
raise SystemExit(2)
""",
        )
        old_env = os.environ.copy()
        os.environ.update(
            {
                "FAKE_STOP": str(stop),
                "FAKE_TODO_STATE": str(state),
                "FAKE_WAKE_LOG": str(wake_log),
            }
        )
        try:
            run_state_aware_wake_loop(
                cli_bin=str(fake_bin / "loopx"),
                tmux_bin=str(fake_bin / "tmux"),
                registry=temp / "registry.json",
                runtime_root=temp / "runtime",
                goal_id="demo-goal",
                session="demo-session",
                lane_agents={
                    "curator": "research-curator",
                    "proposer": "hypothesis-proposer",
                },
                initial_projection=initial,
                artifact=artifact,
                retry_interval_seconds=45.0,
                poll_interval_seconds=0.5,
            )
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        wake_args = json.loads(wake_log.read_text(encoding="utf-8"))
        assert wake_args.count("--lane") == 1, wake_args
        assert wake_args[wake_args.index("--lane") + 1] == "proposer", wake_args
        events = [
            json.loads(line)
            for line in artifact.read_text(encoding="utf-8").splitlines()
        ]
        assert events[0]["mode"] == "todo_readiness_edge_plus_fixed_retry", events
        assert events[1]["trigger"] == "readiness_edge", events
        assert events[1]["target_lanes"] == ["proposer"], events

        codex_args = temp / "codex-args.json"
        prompt = temp / "prompt.txt"
        prompt.write_text("must-not-run-yet", encoding="utf-8")
        write_executable(
            fake_bin / "codex",
            """#!/usr/bin/env python3
import json
import os
import sys
open(os.environ['FAKE_CODEX_ARGS'], 'w', encoding='utf-8').write(json.dumps(sys.argv[1:]))
""",
        )
        env = {
            **os.environ,
            "FAKE_CODEX_ARGS": str(codex_args),
            "LOOPX_CODEX_BIN": str(fake_bin / "codex"),
            "LOOPX_PROJECT": str(temp),
            "LOOPX_CODEX_REASONING_EFFORT": "high",
            "LOOPX_CODEX_TUI_PROMPT_ARTIFACT": str(prompt),
            "LOOPX_CODEX_INITIAL_PROMPT_ENABLED": "0",
        }
        import subprocess

        subprocess.run([sys.executable, "-c", CODEX_TUI_EXEC_PY], env=env, check=True)
        assert "must-not-run-yet" not in json.loads(codex_args.read_text(encoding="utf-8"))

    print("visible multi-agent state-aware wake smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
