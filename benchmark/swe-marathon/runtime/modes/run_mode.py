#!/usr/bin/env python3
"""统一驱动 Codex × LoopX 的三种模式。

    python3 -m modes.run_mode --mode ssh-goal   --project <dir> --task-file <f>
    python3 -m modes.run_mode --mode codex-cli  --project <dir> --task-file <f>
    python3 -m modes.run_mode --mode heartbeat  --project <dir> --task-file <f> --ticks 4

模式取自 LoopX README 的 Codex 三行 host 表；差别见 profiles.py。
`--preflight-only` 走通全部 LoopX 侧契约（渲染 + 闸门 + Goal 挂载）但不起模型
turn，不烧 token，适合当冒烟。

产物是一份 JSON 收据，只含稳定标签、计数、摘要，不含任务原文/轨迹/凭证。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modes.codex_host import CodexHost, classify  # noqa: E402
from modes.profile_install import ProfileError, install as install_profile  # noqa: E402
from modes.profiles import MODES, resolve  # noqa: E402
from modes.session import LoopxSession, SessionError  # noqa: E402


def _default_cli() -> str:
    here = Path(__file__).resolve().parent.parent
    venv = here / ".venv" / "bin" / "loopx"
    return str(venv) if venv.exists() else "loopx"


def _default_codex() -> str:
    here = Path(__file__).resolve().parent.parent
    staged = here / "codex" / "codex"
    return str(staged) if staged.exists() else "codex"


def _default_loopx_src() -> str:
    """默认 LoopX 源根：优先 env MR_LOOPX_ROOT，其次从已安装 loopx 包推导，
    再次回退到仓库根下的 loopx/。不硬编码机器/用户专属布局。"""
    root = os.environ.get("MR_LOOPX_ROOT")
    if root:
        return root
    try:
        import importlib.util
        spec = importlib.util.find_spec("loopx")
        if spec and spec.origin:
            return str(Path(spec.origin).resolve().parent.parent)
    except Exception:
        pass
    return str(Path(__file__).resolve().parent.parent / "loopx")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", required=True, choices=sorted(MODES),
                   help="运行模式")
    p.add_argument("--claim-codex-app", action="store_true",
                   help="heartbeat 模式下硬声明 host_surface=codex_app（上游文档"
                        "意义上的误用，只用于观察 RRULE/ACK 义务如何悬空）")
    p.add_argument("--project", required=True, help="任务工作区（Codex 可见的 cwd）")
    p.add_argument("--task-file", required=True, help="任务正文文件（UTF-8）")
    p.add_argument("--goal-id", default="wen-goal")
    p.add_argument("--agent-id", default="wen-codex")
    p.add_argument("--objective", default=None,
                   help="goal 目标；默认取任务正文首行")
    p.add_argument("--loopx-bin", default=_default_cli())
    p.add_argument("--codex-bin", default=_default_codex())
    p.add_argument("--model", default=os.environ.get("MR_MODEL"))
    p.add_argument("--effort", default=os.environ.get("MR_EFFORT"),
                   help="推理档位，如 xhigh；进 turn/start 的 turn_params.effort")
    p.add_argument("--sandbox", default="danger-full-access")
    p.add_argument("--ticks", type=int, default=1,
                   help="heartbeat 模式的最大唤醒次数；visible 模式恒为 1")
    p.add_argument("--tick-seconds", type=float, default=0.0,
                   help="heartbeat 两次唤醒之间的睡眠秒数")
    p.add_argument("--turn-timeout", type=float, default=1800.0,
                   help="单轮 Goal 预算（秒）")
    p.add_argument("--preflight-only", action="store_true",
                   help="只证 LoopX 契约与 Goal 挂载，不起模型 turn")
    p.add_argument("--loopx-src", default=None,
                   help="LoopX 源码根，用来装隔离 profile；默认 wen/loopx")
    p.add_argument("--profile-root", default=None,
                   help="隔离 profile 装到哪；必须是空目录，默认在 --receipt 旁边")
    p.add_argument("--no-profile", action="store_true",
                   help="不装隔离 profile（body 会引用裸 loopx、技能不装，"
                        "模型多半执行不了——只在调试渲染时用）")
    p.add_argument("--codex-config", default=None,
                   help="provider 配置（config.toml），装完 profile 后拷进它的 "
                        "codex-home；不给的话 app-server 不知道往哪调模型")
    p.add_argument("--require-clean-source", action="store_true",
                   help="要求 LoopX 源码干净才肯装 profile；正式对照应当开")
    p.add_argument("--receipt", default=None, help="收据写到这个文件")
    return p


def _one_turn(session: LoopxSession, host: CodexHost, *, task: str,
              turn_instance: str | None, preflight: bool,
              project: Path) -> dict[str, Any]:
    """一轮：渲染 body → 过闸门 → 交给 codex → 结算。"""

    body = session.render_body(turn_instance=turn_instance)
    objective = body["task_body"]

    decision = session.should_run(turn_instance=turn_instance)
    obligations = session.scheduler_obligations(decision)
    turn: dict[str, Any] = {
        "turn_instance": turn_instance,
        "objective_chars": len(objective),
        "should_run": decision.get("should_run"),
        "effective_action": decision.get("effective_action"),
        "gate_reason": str(decision.get("reason") or "")[:200],
        "scheduler_obligations": obligations,
    }

    if not decision.get("should_run"):
        turn["outcome"] = "gate_declined"
        return turn

    if preflight:
        turn["goal_receipt"] = host.preflight(
            cwd=str(project), objective=objective, task_instruction=task,
            process_cwd=str(project),
        )
        turn["outcome"] = "preflight_only"
        return turn

    receipt = host.run(cwd=str(project), objective=objective,
                       task_instruction=task, process_cwd=str(project))
    turn["goal_receipt"] = receipt
    classification = classify(receipt)
    turn["classification"] = classification
    turn["settlement"] = _compact_settlement(session.settle(
        classification=classification,
        todo_id=session.selected_todo_id(decision),
    ))
    turn["outcome"] = "ran"
    return turn


def _compact_settlement(settled: dict[str, Any]) -> dict[str, Any]:
    """结算结果只留可公开的状态位。"""

    spend = settled.get("spend_slot") or {}
    refresh = settled.get("refresh_state") or {}
    before = spend.get("before") or {}
    quota = before.get("quota") or {}
    return {
        "refresh_ok": refresh.get("ok"),
        "spend_ok": spend.get("ok"),
        # agent 在 turn 内自己结算过时 spend_ok=false 是正常的，reason 说明原因
        "spend_reason": str(spend.get("reason") or "")[:160] or None,
        "spent_slots_total": quota.get("spent_slots"),
        "quota_state": quota.get("state") or before.get("state"),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    mode = resolve(args.mode, claim_codex_app=args.claim_codex_app)
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"FATAL: --project 不是目录: {project}", file=sys.stderr)
        return 2
    task = Path(args.task_file).read_text(encoding="utf-8").strip()
    if not task:
        print("FATAL: --task-file 是空的", file=sys.stderr)
        return 2
    objective = args.objective or task.splitlines()[0][:200]

    # ── 隔离 profile：一次给齐上游要求的三项产品路径证据 ──────────────────
    # 1) 本模式渲染的 Goal body  2) 技能装进 app-server 实际用的 CODEX_HOME
    # 3) body 里点名的那个 release CLI 真的存在
    installed = None
    if not args.no_profile:
        src = args.loopx_src or _default_loopx_src()
        root = args.profile_root or str(
            Path(args.receipt).resolve().parent / f"profile-{mode.name}"
            if args.receipt else Path(f"/tmp/wen-profile-{mode.name}-{os.getpid()}")
        )
        try:
            installed = install_profile(src, root, python_executable=sys.executable,
                                        require_clean_source=args.require_clean_source)
        except ProfileError as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            return 2
        if args.codex_config:
            dest = Path(installed.codex_home) / "config.toml"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(Path(args.codex_config).read_text(encoding="utf-8"),
                            encoding="utf-8")

    cli = installed.cli_bin if installed else args.loopx_bin
    session = LoopxSession(cli=cli, project=project, goal_id=args.goal_id,
                           agent_id=args.agent_id, mode=mode,
                           cli_bin=installed.cli_bin if installed else "",
                           env=installed.env() if installed else {})
    host = CodexHost(codex_bin=args.codex_bin, mode=mode, model=args.model,
                     effort=args.effort, sandbox=args.sandbox,
                     goal_timeout_sec=args.turn_timeout,
                     required_skill_ids=installed.required_skill_ids if installed else (),
                     process_env=installed.env() if installed else None)

    out: dict[str, Any] = {
        "schema": "wen_mode_run_v0",
        "mode": mode.name,
        "runtime_profile": mode.runtime_profile,
        "scheduler_context": {
            "host_surface": mode.host_surface,
            "scheduler_owner": mode.scheduler_owner,
            "execution_mode": mode.execution_mode,
        },
        "continuation_owner": mode.continuation_owner,
        "substitution": mode.substitution or None,
        "notes": mode.notes,
        "model": args.model,
        "effort": args.effort,
        "preflight_only": bool(args.preflight_only),
        "loopx_profile": installed.receipt() if installed else None,
        "turns": [],
    }

    try:
        session.bootstrap(objective)
        # 任务必须作为 todo 进 goal —— 闸门按 todo 选工作，只放进 turn 输入的话
        # 模型没有可执行 todo，会跑满预算却零产出且不报错。
        session.add_task_todo(task)
    except SessionError as exc:
        out["error"] = f"bootstrap 失败: {exc}"
        _emit(out, args.receipt)
        return 1

    # visible Goal 由 Codex 自己续跑，驱动只起一轮；心跳由驱动按节拍唤醒。
    ticks = args.ticks if mode.continuation_owner == "driver" else 1

    for i in range(ticks):
        if i and args.tick_seconds:
            time.sleep(args.tick_seconds)
        ti = session.new_turn_instance() if mode.needs_turn_instance else None
        try:
            turn = _one_turn(session, host, task=task, turn_instance=ti,
                             preflight=args.preflight_only, project=project)
        except Exception as exc:  # noqa: BLE001 — 收据要如实记录失败
            turn = {"turn_instance": ti, "outcome": "error",
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        out["turns"].append(turn)
        if turn.get("outcome") == "error":
            break
        # Goal 已到终态就不用再唤醒
        receipt = turn.get("goal_receipt") or {}
        if str(receipt.get("post_goal_status") or "") not in ("", "active"):
            out["stopped_early"] = "goal_left_active"
            break

    out["turns_run"] = len(out["turns"])
    _emit(out, args.receipt)
    return 0 if out["turns"] and out["turns"][-1].get("outcome") != "error" else 1


def _emit(payload: dict[str, Any], path: str | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    print(text)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
