#!/usr/bin/env python3
"""把保留的公开模式聚合成单一 data.json，供可视化网页与总结 md 使用。

口径全部走 scripts/_common（模式名归一化、只认 job 级 result.json、属主校验、半成品
metrics 排除、cost 取 cost_usd）。cost 以 result.json 的 cost_usd 为准（不是 0）。

用法：
    _aggregate.py <out_dir> [data.json]
    _aggregate.py marathon-full viz/data.json
"""

from __future__ import annotations

import json
import os
import sys

from _common import PUBLIC_ARMS as ARMS, PUBLICATION_NOTE, collect, mean, safe_path

# 模式的角色标注，写进 data.json 供前端解释
ARM_ROLE = {
    "plain": "baseline①：裸 codex，objective = 'Finish the task.'，无 goal、无 LoopX",
    "goal": "baseline②：codex 原生 goal（codex 自带的 goal 功能，注入干净 goal，非 LoopX）",
    "heartbeat": "LoopX 模式③：心跳驱动的续跑/解锁 + LoopX goal body/skills",
}


def _mode_summary(rs: list) -> dict:
    """单个模式的汇总。

    reward/partial/testrate 在**全部匹配任务**上取均值（不做单臂剔除）——所有模式
    共用保留模式齐备的任务分母，避免不匹配分母。构建失败作为观测结果计入，
    另用 build_failed 单独计数标注，不改分母。
    """
    return {
        "n": len(rs),
        "reward": mean([x["reward"] for x in rs]),
        "partial": mean([x["partial"] for x in rs]),
        "testrate": mean([x["testrate"] for x in rs]),
        "cost": round(sum(x["cost"] for x in rs), 2),
        "tok_in": sum(x["tok_in"] for x in rs),
        "tok_out": sum(x["tok_out"] for x in rs),
        "build_failed": sum(1 for x in rs if x["build_failed"]),
        "self_complete": sum(1 for x in rs if x.get("status") == "complete"),
        "cont_total": sum((x.get("cont") or 0) for x in rs),
        "unblock_total": sum((x.get("unblock") or 0) for x in rs),
        "wall_min": round(sum((x.get("min") or 0) for x in rs), 1),
    }


def main() -> int:
    root = safe_path(sys.argv[1] if len(sys.argv) > 1 else "marathon-full")
    outp = safe_path(sys.argv[2] if len(sys.argv) > 2 else "viz/data.json")
    cur = {key: rec for key, rec in collect(root).items() if key[1] in ARMS}
    if not cur:
        print("没有结果", file=sys.stderr)
        return 1

    tasks = sorted({t for t, _ in cur})
    full = [t for t in tasks if all((t, a) in cur for a in ARMS)]

    cells: dict = {}
    for (task, arm), rec in cur.items():
        cells.setdefault(task, {})[arm] = rec

    arm_summary = {}
    for a in ARMS:
        rs = [cur[(t, a)] for t in full if (t, a) in cur]
        summary = _mode_summary(rs)
        summary["role"] = ARM_ROLE[a]
        arm_summary[a] = summary

    data = {
        "generated_at": None,          # 由外部盖时间戳；脚本内不取系统时钟
        "bench": os.environ.get("WEN_BENCH", "swe-marathon"),
        "arms": list(ARMS),
        "arm_role": ARM_ROLE,
        "tasks_all": tasks,
        "tasks_full": full,
        "n_trials": len(cur),
        "arm_summary": arm_summary,
        "cells": {t: {a: cells[t].get(a) for a in ARMS if a in cells[t]} for t in tasks},
        "publication_note": PUBLICATION_NOTE,
    }
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"写出 {outp}：{len(tasks)} 任务，{len(full)} 保留模式齐，{len(cur)} trial")
    for a in ARMS:
        s = arm_summary[a]
        print(f"  {a:10} reward={s['reward']!s:>6} partial={s['partial']!s:>7} "
              f"cost=${s['cost']:<7} 自收工={s['self_complete']}/{s['n']} "
              f"续跑={s['cont_total']} 解锁={s['unblock_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
