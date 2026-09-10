#!/usr/bin/env python3
"""五模式评测脚本的公共件：模式名归一化、连续分口径、结果收集、路径校验。

抽出来是为了让 _compare / _partial / _summarize / _aggregate / _extract_traj 复用同一
份口径（避免同一个 bug 在多个脚本里各修一遍），也消除重复代码。改这里等于同时改所有
下游报表，动前先想清楚。
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re

# 五个模式：2 条 baseline（plain=裸 codex、goal=codex 原生 goal）+ 3 个 LoopX 模式
ARMS = ("plain", "goal", "ssh-goal", "codex-cli", "heartbeat")

# Publication scope only: runner support and private collection remain unchanged.
PUBLIC_ARMS = ("plain", "goal", "heartbeat")
PUBLICATION_NOTE = (
    "The ssh-goal and codex-cli groups and conclusions are withdrawn pending validation. "
    "This publication retains plain, goal, and heartbeat only; private raw results are unchanged."
)


def norm(name: str) -> str:
    """模式名归一化：ssh-goal-1537631 → ssh-goal。

    marathon_run.sh 在原目录不可写时会回退成 `<mode>-<pid>`。不归一化的话这些结果
    的 key 不在 ARMS 白名单里，下游打印循环会静默跳过——结果存在但表里看不见。
    """
    return re.sub(r"-\d{3,}$", "", name)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def safe_path(arg: str) -> pathlib.Path:
    """把命令行传入的路径规范化成绝对路径再交给下游访问。

    先 expanduser + resolve 把 `..`、符号链接、`~` 都折叠掉，得到一个确定的规范
    路径，避免"用未经处理的原始参数直接拼路径去读写文件"。这些脚本本就是对任意
    结果目录/输出文件工作的 CLI，不额外限制根目录，只保证路径是规范化后的。
    """
    return pathlib.Path(arg).expanduser().resolve()


def testrate(d: dict):
    """测试通过率——比 partial_score 更稳的连续口径。

    优先 pytest 分组的 passed/total，其次顶层 passed/total，再次 passed/(passed+failed)
    （cargo test 只写这俩），最后 gates_passed/gates_total。都没有返回 None。
    """
    pt = d.get("pytest")
    if isinstance(pt, dict) and pt:
        groups = [g for g in pt.values() if isinstance(g, dict)]
        p = sum((g.get("passed") or 0) for g in groups)
        t = sum((g.get("total") or 0) for g in groups)
        if t:
            return p / t
    p, t, f = d.get("passed"), d.get("total"), d.get("failed")
    if isinstance(p, (int, float)) and isinstance(t, (int, float)) and t:
        return p / t
    if isinstance(p, (int, float)) and isinstance(f, (int, float)) and (p + f):
        return p / (p + f)
    gp, gt = d.get("gates_passed"), d.get("gates_total")
    if isinstance(gp, (int, float)) and isinstance(gt, (int, float)) and gt:
        return gp / gt
    return None


def score(d: dict):
    """连续分：优先 partial_score，回退 pass_rate。两者都没有返回 None。"""
    for k in ("partial_score", "pass_rate"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _load(p: pathlib.Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _wall_minutes(d: dict):
    try:
        t0 = datetime.datetime.fromisoformat(d["started_at"])
        t1 = datetime.datetime.fromisoformat(d["finished_at"])
        return round((t1 - t0).total_seconds() / 60, 1)
    except Exception:
        return None


def collect(root: pathlib.Path) -> dict:
    """收集每个 (任务, 模式) 的完整记录，键为 (task, arm)。

    口径（都踩过坑，别退回去）：
      · 只认 job 级 result.json（有 stats、n_completed_trials≥1）
      · 属主必须是当前用户（排除上一轮 root 属主的遗留目录）
      · partial 半成品（phase=initialized/starting）不算成绩
      · cost 取 stats.cost_usd
    返回的是超集记录，_compare 与 _aggregate 各取所需字段。
    """
    out: dict = {}
    if not root.is_dir():
        return out
    for r in root.glob("*/*/*/*/result.json"):
        rel = r.relative_to(root).parts
        task, armdir = rel[0], rel[1]
        if task.startswith("."):
            continue
        arm = norm(armdir)
        if arm not in ARMS:
            continue
        try:
            if (root / rel[0] / rel[1]).stat().st_uid != os.getuid():
                continue
        except OSError:
            continue
        d = _load(r)
        if not d:
            continue
        s = d.get("stats", {})
        if not s or int(s.get("n_completed_trials") or 0) < 1:
            continue
        rw = [float(k)
              for ev in (s.get("evals") or {}).values()
              for k, tasks in ((ev.get("reward_stats") or {}).get("reward") or {}).items()
              for _ in tasks]
        rec = {
            "task": task, "arm": arm,
            "reward": rw[0] if rw else None,
            "cost": s.get("cost_usd") or 0.0,
            "tok_in": s.get("n_input_tokens") or 0,
            "tok_out": s.get("n_output_tokens") or 0,
            "tok_cache": s.get("n_cache_tokens") or 0,
            "errors": int(s.get("n_errored_trials") or 0),
            "min": _wall_minutes(d),
            "partial": None, "testrate": None, "build_failed": False,
            "passed": None, "failed": None,
            "status": None, "cont": None, "unblock": None, "err_events": None,
            "run_dir": str(r.parent.relative_to(root)),
        }
        for m in r.parent.glob("*/verifier/metrics.json"):
            mm = _load(m)
            if not mm:
                continue
            ph = str(mm.get("phase") or "")
            if ph in ("initialized", "starting"):
                continue
            rec["partial"] = mm.get("partial_score")
            rec["testrate"] = testrate(mm)
            rec["build_failed"] = ph == "build_failed"
            rec["passed"], rec["failed"] = mm.get("passed"), mm.get("failed")
        for f in r.parent.glob("*/agent/goal_receipt.json"):
            g = _load(f)
            if not g:
                continue
            rec["status"] = g.get("post_goal_status")
            rec["cont"] = g.get("goal_continuation_turn_completed_count")
            rec["unblock"] = g.get("_unblock_count")
            rec["err_events"] = g.get("error_event_count")
        out[(task, arm)] = rec
    return out
