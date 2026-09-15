"""plain 臂：走 app-server，但**不挂 Goal、不装 LoopX**。

## 为什么要有这个文件

原来的 plain 臂用 `codex exec`（流式 SSE），其余四臂走 app-server（JSON-RPC）。
实测这条 SSE 通道在上游极不稳定，plain **2/2 全错**而其余四臂 0 失败，
四轮下来被多种不同的传输层错误反复打死（限流 / 参数 400 / 模型名 400 / 空错误）。

这些全是**传输层**问题。照原样跑完，五臂对比会显示"plain 最差"，
但那是通道差异不是 harness 差异 —— 会得出假结论。

## 这个变体改了什么、没改什么

改：传输从 `codex exec` 换成 app-server（与其余四臂一致）。
没改：**不挂 Goal**（不发 thread/goal/set）、**不装 LoopX**、同一个 codex 二进制、
      同样的 model/effort/sandbox/工具面。

所以它仍然是"什么都不加的 codex"——只是用 JSON-RPC 而不是命令行驱动。
报分时必须注明这一点：plain 的传输与基线论文的 `codex exec` 不同。

## 与 CodexGoalAgent 的唯一区别

复用它的全部装配与驱动逻辑，只把 `start_native_goal_turn`（挂 Goal + 起 turn）
换成 `_start_turn_without_goal`（只起 turn）。
"""

from __future__ import annotations

from typing import Any

from loopx.capabilities.benchmark_toolkit.native_codex_goal import (
    NativeGoalConfig,
    NativeGoalProtocolError,
    NativeGoalTurn,
    _nested,
)

from codex_goal_agent import CodexGoalAgent


def _start_turn_without_goal(transport, config: NativeGoalConfig) -> NativeGoalTurn:
    """initialize → thread/start → turn/start，**跳过 thread/goal/set**。

    照抄 start_native_goal_turn 的参数构造，只去掉 attach_native_goal 那一步，
    保证除"有没有 Goal"之外的一切与 goal 臂逐字一致。
    """

    transport.request("initialize", {
        "clientInfo": {"name": "wen_plain_appserver",
                       "title": "wen plain (app-server, no Goal)",
                       "version": "0.1.0"},
        "capabilities": {"experimentalApi": True},
    })
    transport.notify("initialized", {})

    thread_params: dict[str, Any] = {
        "cwd": config.cwd,
        "sandbox": config.sandbox,
        "approvalPolicy": config.approval_policy,
    }
    if config.model:
        thread_params["model"] = config.model
    thread_result = transport.request("thread/start", thread_params)
    thread = _nested(thread_result, "thread")
    thread_id = str(thread.get("id") or thread_result.get("threadId") or "")
    if not thread_id:
        raise NativeGoalProtocolError("thread_start_id_missing")

    turn = NativeGoalTurn(
        thread_id=thread_id,
        turn_id="",
        response_turn_id="",
        goal_status="none",          # 本臂没有 Goal
        objective_sha256="",
        objective_chars=0,
        task_instruction_sha256="",
        task_instruction_chars=len(config.task_instruction),
        token_budget_present=False,
        methods=["initialize", "initialized", "thread/start"],
    )

    turn_params: dict[str, Any] = {
        "threadId": thread_id,
        "input": [{"type": "text", "text": config.task_instruction}],
        "cwd": config.cwd,
        "approvalPolicy": config.approval_policy,
    }
    if config.model:
        turn_params["model"] = config.model
    if config.effort:
        turn_params["effort"] = config.effort
    if config.sandbox_policy is not None:
        turn_params["sandboxPolicy"] = dict(config.sandbox_policy)
    turn_result = transport.request("turn/start", turn_params)
    turn.methods.append("turn/start")
    response_turn = _nested(turn_result, "turn")
    rid = str(response_turn.get("id") or turn_result.get("turnId") or "")
    if not rid:
        raise NativeGoalProtocolError("turn_start_id_missing")
    turn.turn_id = rid
    turn.response_turn_id = rid
    turn.turn_status = str(response_turn.get("status") or "accepted")
    return turn


class CodexPlainAppServer(CodexGoalAgent):
    """plain 臂：app-server 传输，无 Goal、无 LoopX。"""

    @staticmethod
    def name() -> str:
        return "codex-plain-appserver"

    def _drive(self, transport, config):
        """只起一轮 turn 并等它结束；没有 Goal 就没有续跑。"""
        from loopx.capabilities.benchmark_toolkit.native_codex_goal import (
            wait_native_goal_turn,
        )
        import time as _t

        turn = _start_turn_without_goal(transport, config)
        self._turn = turn
        # 无 Goal → codex 不会自动续跑，等这一轮结束即可
        try:
            wait_native_goal_turn(transport, turn,
                                  timeout_sec=self._goal_timeout_sec())
        except NativeGoalProtocolError as exc:
            if str(exc) != "goal_turn_timeout":
                raise
        return turn

    def _goal_timeout_sec(self) -> float:
        from codex_goal_agent import _GOAL_TIMEOUT_SEC
        return _GOAL_TIMEOUT_SEC
