"""LoopX 侧的一轮：渲染 body → 过闸门 → 结算。

对三种模式一视同仁；模式差别全部来自 profiles.Mode，本模块不写 if mode ==。

刻意不复用 benchmark_toolkit.native_codex_profile.render_native_codex_goal_prompt：
那个函数把 `codex_app_ssh_goal` 写死在三处（native_codex_profile.py:337-338、366、
399），换 profile 就会在 `runtime_profile != "codex_app_ssh_goal"` 那道断言上失败。
这里直接调同一个 CLI 子命令，把 profile 参数化，其余校验照抄它的意图。
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .profiles import Mode, profile_args

#: body 里出现这些字样说明 LoopX 认为该模式是 visible Goal 而非心跳自动化。
_VISIBLE_MARKER = "visible Codex"
#: 心跳 body 会要求宿主提供 turn instance。
_TURN_ENV = "LOOPX_TURN"


class SessionError(RuntimeError):
    """LoopX 侧的一轮没能按契约走完。"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LoopxSession:
    """绑定到一个 goal + agent 的 LoopX 会话。"""

    cli: str
    """执行用的 loopx 可执行文件路径。"""

    project: Path
    goal_id: str
    agent_id: str
    mode: Mode
    cli_bin: str = ""
    """写进 body 的 CLI 路径（--cli-bin）。留空则 body 里渲染成裸 `loopx`。"""
    timeout_sec: float = 120.0
    env: dict[str, str] = field(default_factory=dict)

    # ── 底层 ────────────────────────────────────────────────────────────────
    def _run(self, args: list[str], *, extra_env: dict[str, str] | None = None,
             expect_ok: bool = True) -> dict[str, Any]:
        """跑一条 loopx 子命令，要求 --format json 且能解析。

        expect_ok 默认开：loopx 的写命令失败时**照样退出 0**，只在 JSON 里把
        ok 置 false。不查这一位的话，写不进去的 todo、注册不上的 agent 都会静默
        通过，一直到几百秒后模型行为不对才发现。
        """

        argv = [self.cli, "--format", "json", *args]
        run_env = {**os.environ, **self.env, **(extra_env or {})}
        proc = subprocess.run(
            argv,
            cwd=str(self.project),
            capture_output=True,
            text=True,
            timeout=self.timeout_sec,
            env=run_env,
        )
        text = proc.stdout.strip()
        # loopx 的 json 输出有时包在 ``` 围栏里
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        if not text:
            raise SessionError(
                f"loopx {' '.join(args[:2])} 无输出 (exit={proc.returncode}): "
                f"{proc.stderr.strip()[:300]}"
            )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SessionError(
                f"loopx {' '.join(args[:2])} 输出不是 JSON: {text[:300]}"
            ) from exc
        if expect_ok and isinstance(payload, dict) and payload.get("ok") is False:
            raise SessionError(
                f"loopx {' '.join(args[:2])} 失败: "
                f"{str(payload.get('error'))[:400]}"
            )
        return payload

    # ── 一次性准备 ──────────────────────────────────────────────────────────
    def bootstrap(self, objective: str) -> dict[str, Any]:
        """建 goal 并把本 agent 注册进 coordination.registered_agents。

        注册这步不能省：不注册的话 heartbeat-prompt 会返回 ok=false，错误信息是
        "cannot be used because goal has no coordination.registered_agents list"，
        而它仍然退出 0，很容易被当成渲染成功。

        bootstrap 不再写入任何首连 onboarding todo（user gate / 候选 todo /
        connection validation 都已删除），所以接 goal 之后闸门里不会再有
        需要人工放行的条目，无人值守环境也不会静默空转。
        """

        boot = self._run([
            "bootstrap",
            "--project", ".",
            "--goal-id", self.goal_id,
            "--objective", objective,
        ])
        self._run([
            "configure-goal",
            "--goal-id", self.goal_id,
            "--registered-agent", self.agent_id,
            "--execute",
        ])
        return boot

    def add_task_todo(self, task_text: str, *, todo_id: str = "wen-task") -> dict[str, Any]:
        """把任务正文作为一条 P0 agent todo 写进 goal。

        这一步不能省，也不能只靠 turn/start 的输入：闸门是按 todo 选工作的，
        任务不在 todo 里就不会被选中。实测过只把任务放进 turn 输入的情况，900 秒
        里只建了 .loopx/ 和 .codex/，任务文件一个字没改，而且不报错——闸门放行、
        Goal 活着、收据干净，看起来一切正常。

        闸门是按 todo 选工作的，任务不在 todo 里就不会被选中。
        """

        return self._run([
            "todo", "add",
            "--goal-id", self.goal_id,
            "--role", "agent",
            "--todo-id", todo_id,
            "--text", task_text,
            "--task-class", "advancement_task",
            "--status", "open",
            "--execute",
        ])

    # ── 每轮 ────────────────────────────────────────────────────────────────
    def render_body(self, *, turn_instance: str | None = None) -> dict[str, Any]:
        """渲染本模式的 task_body，并校验它确实属于本模式。"""

        args = [
            "heartbeat-prompt", "--thin",
            "--goal-id", self.goal_id,
            "--agent-id", self.agent_id,
            *profile_args(self.mode),
        ]
        # body 里会写"用 `<cli_bin> ...` 跑下一步"。不传的话渲染成裸 `loopx`，
        # 模型会去 PATH 上找——那多半是另一个安装、另一个 registry。实测这条不传
        # 的后果是模型拿到一份自己执行不了的指令，跑满预算、零改动、且不报错。
        if self.cli_bin:
            args += ["--cli-bin", self.cli_bin]

        if self.mode.needs_turn_instance:
            if not turn_instance:
                raise SessionError(
                    f"{self.mode.name} 每轮需要 turn instance（body 里会引用 "
                    f"{_TURN_ENV}），调用方没给"
                )
            args += ["--turn-instance-id", turn_instance]

        payload = self._run(args, extra_env={_TURN_ENV: turn_instance} if turn_instance else None)

        if not payload.get("ok"):
            raise SessionError(
                f"heartbeat-prompt 失败({self.mode.name}): "
                f"{str(payload.get('error'))[:400]}"
            )
        body = (payload.get("task_body") or "").strip()
        if not body:
            raise SessionError(f"heartbeat-prompt 没给 task_body({self.mode.name})")

        self._assert_body_matches_mode(body, payload)
        return payload

    def _assert_body_matches_mode(self, body: str, payload: dict[str, Any]) -> None:
        """确认渲染出来的确实是本模式的 body，而不是别的模式的。

        这一条是仿 native_codex_profile.py:366 的 runtime_profile 断言。渲染器按
        profile 分岔（visible-Goal vs 心跳派发器），拿错了不会报错、只会静默测成
        另一个模式——那种失败最难发现，所以在这里挡住。
        """

        visible = _VISIBLE_MARKER in body
        if self.mode.continuation_owner == "codex" and not visible:
            raise SessionError(
                f"{self.mode.name} 期望 visible Goal body，实际拿到的不含"
                f"{_VISIBLE_MARKER!r}——渲染 profile 可能没生效"
            )
        if self.mode.continuation_owner == "driver" and visible:
            raise SessionError(
                f"{self.mode.name} 期望心跳派发器 body，实际拿到的是 visible Goal body"
            )

        spend = payload.get("quota_spend_command") or ""
        want = f"--source {self.mode.spend_source}"
        if want not in spend:
            raise SessionError(
                f"{self.mode.name} 的 spend 命令应含 {want!r}，实际: {spend[:200]}"
            )

    def should_run(self, *, turn_instance: str | None = None) -> dict[str, Any]:
        """闸门。返回完整决策，调用方读 should_run / interaction_contract。"""

        args = [
            "quota", "should-run",
            "--goal-id", self.goal_id,
            "--agent-id", self.agent_id,
            *profile_args(self.mode),
        ]
        if self.mode.needs_turn_instance:
            if not turn_instance:
                raise SessionError(f"{self.mode.name} 的闸门需要 turn instance")
            args += ["--turn-instance-id", turn_instance]
        return self._run(args, extra_env={_TURN_ENV: turn_instance} if turn_instance else None)

    @staticmethod
    def selected_todo_id(decision: dict[str, Any]) -> str:
        """闸门这一轮选中的 todo。

        visible Goal 的结算要求绑定恰好一个 todo_id，否则 spend-slot 回
        "visible Goal settlement requires exactly one todo_id or
        replan_obligation_id binding"。
        """

        sel = (decision.get("selected_todo") or {})
        return str(sel.get("todo_id") or "")

    def settle(self, *, classification: str, todo_id: str = "") -> dict[str, Any]:
        """一轮做完之后写回状态并花一次配额。

        顺序不能反：LoopX 的契约是 spend_only_after_artifact_validation_writeback，
        先 refresh-state 再 spend-slot。

        **两步都不强制成功**。visible Goal 模式下 body 本身就要求 agent 在 turn 内
        自己 refresh + spend，等驱动来收尾时 goal 往往已经是 terminal_no_followup、
        配额也已经花过（实测 spent_slots=2）。这时再 spend 会返回 ok=false，
        reason 是"validated closure evidence derives terminal no-follow-up..."——
        那是**正常的已结算**，不是失败。强行当错误处理会把一次成功的跑判成失败。
        """

        refresh = self._run([
            "refresh-state",
            "--goal-id", self.goal_id,
            "--agent-id", self.agent_id,
            "--project", ".",
            "--classification", classification,
        ], expect_ok=False)
        spend_args = [
            "quota", "spend-slot",
            "--goal-id", self.goal_id,
            "--agent-id", self.agent_id,
            "--slots", "1",
            "--source", self.mode.spend_source,
            "--execute",
        ]
        if todo_id:
            spend_args += ["--todo-id", todo_id]
        spend = self._run(spend_args, expect_ok=False)
        return {"refresh_state": refresh, "spend_slot": spend}

    # ── 心跳专用 ────────────────────────────────────────────────────────────
    @staticmethod
    def new_turn_instance() -> str:
        """心跳每次唤醒用一个新的 turn instance；重试复用同一个。"""

        return _utc_now_iso()

    @staticmethod
    def scheduler_obligations(decision: dict[str, Any]) -> dict[str, Any]:
        """从闸门决策里摘出宿主该兑现的调度义务。

        对 local_scheduler，这里应该是空的（cadence 由宿主自己拥有）。
        对硬声明 codex_app 的变体，这里会有 apply_needed/ack_needed——本驱动没有
        真 App 可以 automation_update，所以只记录、不假装兑现。
        """

        hint = decision.get("scheduler_hint") or {}
        app = hint.get("codex_app") or {}
        backoff = app.get("stateful_backoff") or {}
        return {
            "applicability": app.get("applicability"),
            "apply_needed": backoff.get("apply_needed"),
            "ack_needed": backoff.get("ack_needed"),
            "recommended_rrule": backoff.get("recommended_rrule"),
            "host_action": app.get("host_action"),
        }
