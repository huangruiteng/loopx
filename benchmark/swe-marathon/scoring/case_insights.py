#!/usr/bin/env python3
"""把公开模式聚合（data.json）里的观察，投影成**非官方 draft** 记录
`swe_marathon_case_insight_draft_v0`（见 upstream #3878 / RFC #3812）。

【为什么是 draft，不是官方 projection】
官方 `benchmark_case_insight_projection_v0` 定义的是“某一个 exact terminal run 的
child record”：正式上传 `simulate_benchmark_upload()` 会先 `_validate_case_insight_attachment()`，
要求同 benchmark/study/run_id 下**恰好存在一个 active terminal
`benchmark_experiment_board_row_v0`**，且 case/outcome/`insight.status=complete` 全部匹配。
本仓库没有这些 run 的 board row，也没有生产调用方，正式记录会在 preview 阶段被
`ValueError: case-insight upload requires one active exact-run board record` 拒绝。
因此本脚本刻意产出**独立可读的 draft**：字段形状对齐官方（便于后续提升），但
`schema_version` 明示为 draft、不声称可进入 provider 生命周期。补齐 board row 后
可将 `schema_version` 提升为官方值并走 attachment（见 test 的 promotion 用例 + README 血缘）。

【身份口径】data.json 由 `_common.collect()` 折叠为 latest-attempt-per-(task,arm)
（`out[(task,arm)]=rec`），attempt 维度在生成 data.json 时已收敛为“该格最后一次”。
故 `_run_id` 对**存活 attempt 的 run_dir 取短哈希**：既是 exact-per-attempt 身份
（不同 run_dir → 不同 id，不再把所有重跑折叠成 `task__arm`），又不泄露 wall-clock
时间戳。完整多 attempt 保留需要改 collect/aggregate，属后续工作。

用法（固定读写脚本所属 benchmark 目录下的 data.json → case_insights.json）：
    python3 case_insights.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

from _common import PUBLIC_ARMS

# 脚本所属 benchmark 目录（benchmark/swe-marathon）；输入/输出固定落在此处，
# 不从命令行参数拼路径（避免用户可控数据构造文件路径 —— SonarCloud S2083）。
_BASE = pathlib.Path(__file__).resolve().parent.parent

# 非官方 draft schema；OFFICIAL_SCHEMA 是补齐 board row 后的提升目标。
SCHEMA = "swe_marathon_case_insight_draft_v0"
OFFICIAL_SCHEMA = "benchmark_case_insight_projection_v0"
STUDY_ID = "codex-loopx-access-modes"
# draft 的 outcome 词表：completed / runner_invalid 与官方同义；incomplete 是 draft
# 专有——“有测量但未达终态”，用于区分**运行侧失败**（无可计结果）与**未 finalize**。
OUTCOMES = {"completed", "runner_invalid", "incomplete"}
_COMPLETE = "complete"
# automation-recovers 的“达终态且接近满分”门槛。钉在 0.99：只有 automation 模式几乎打满、
# 且**有效** plain 基线明显更低（gap≥_RECOVER_MIN_GAP）时才算“帮基线补上长尾”，避免把
# 噪声级差异当成 automation 增益。
_STABLE_MIN = 0.99
# 文本上限放宽到 1200：审阅希望 insight 写厚一些（因果/影响/下一步都给足空间）。
_TEXT_LIMIT = 1200


def _clip(s: str, limit: int = _TEXT_LIMIT) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= limit else s[:limit - 1] + "…"


def _run_id(run_dir: str, task: str, arm: str) -> str:
    """从 run_dir 派生稳定、exact-per-attempt、public-safe 的 run 句柄。

    run_dir 形如 `task/arm/<stamp>/arm`：`<stamp>` 是 wall-clock，属私有细节，故对
    **整段 run_dir 取短哈希**附到 `task__arm` 后。这样不同 attempt 的 run_dir 得到
    不同 id（不再把同 (task,arm) 的所有重跑折叠成同一句柄），而公开产物里既无原始
    时间戳也无原始路径。run_dir 缺失时退回 `task__arm`。
    """
    base = re.sub(r"[^A-Za-z0-9._-]", "-", f"{task}__{arm}").strip("-._")
    if run_dir:
        # 仅作稳定的 public-safe 标识符（非加密用途）；用 sha256 取前 8 位十六进制。
        digest = hashlib.sha256(run_dir.encode("utf-8")).hexdigest()[:8]
        return f"{base}__{digest}"
    return base


def _outcome_status(cell: dict) -> str:
    """把 goal-receipt 状态映射到 draft 的 outcome —— **fail-closed**。

    build_failed → runner_invalid（构建失败，确无可计能力结果）。
    status=complete → completed。
    status∈{blocked, active} → incomplete（有测量/续跑但未达终态；**不**当作
      runner 失败：有实测分数但未完成，不能等同于没有可计结果）。
    其余未知 status → 抛错，拒绝像旧版那样把未知值静默归入 runner_invalid。
    """
    if cell.get("build_failed"):
        return "runner_invalid"
    status = cell.get("status")
    if status == _COMPLETE:
        return "completed"
    if status in ("blocked", "active"):
        return "incomplete"
    raise ValueError(f"未知 cell status={status!r}；fail-closed 拒绝静默归类")


def _build_failed_insight(task: str, arm: str) -> tuple:
    return ("build_failed_gate_zeroed",
            (f"{arm} 在 {task} 的构建阶段失败，agent 未能产出可编译/可运行的成品，"
             f"partial_score 被评分门禁归零。这是运行/环境侧的结果（镜像、依赖、"
             f"构建超时或 agent 留下不可编译的代码），并非该模型在此任务上的能力定论；"
             f"同一格在不同 attempt 下可能构建成功。"),
            ("该格作为观测计入 matched 分母并单列标注，不做单模式剔除——剔除会系统性"
             "偏袒‘构建更容易失败’的模式。报分时应把 build_failed 作为独立类目呈现，"
             "而不是把它混入能力低分。"),
            ("重复运行以区分偶发构建失败与稳定失配；必要时对齐镜像/依赖版本、放宽构建"
             "超时，并核对 agent 末态代码是否可编译。"),
            "unexpected", "medium")


def _idle_churn_insight(task: str, arm: str, unblock: int, cont: int, partial) -> tuple:
    return ("unattended_continuation_idle_churn",
            (f"{arm} 在 {task} 的多轮续跑出现重复解锁：unblock={unblock}、cont={cont}、"
             f"终态未 {_COMPLETE}（partial={partial}）。这些计数是描述性观察，"
             "尚不能确定失败原因或据此比较其他接入模式。"),
            ("额外续跑未保证完成；需要区分有效工作与重复解锁，并保留此负例。"),
            ("核查每次解锁后的实际工作与回合边界，再做匹配重复实验。"),
            "unexpected", "medium")


# 经人工轨迹分析核实的 good case（数字来自各模式 agent 轨迹的 step 数，public-safe 聚合，
# 无 raw）。只有在**数据侧条件也成立**（automation 完成且 plain 有效基线明显更低）时才挂上，
# 保证记录可从 data.json 复算、curated 文本只补轨迹层面的“怎么帮的”。
_GOOD_CASE_NOTES = {
    ("zstd-decoder", "heartbeat"): (
        "轨迹对照：plain 在 6 个可见 fixture 通过后即于第 52 step 宣布“Implemented the complete "
        "RFC 8878 decoder”收工（hidden 25/37）——典型的“可见信号变绿即停”。heartbeat 在同一可见-通过点"
        "没有停：LoopX 续跑循环反复注入 goal、驳回其 update_goal=complete，把运行推到 453 step。这段续跑里 "
        "agent 自建了一套 RFC-derived 验收程序（156 项检查，远超 6 个 fixture）、转入内存安全审计，并定位/修复"
        "了具体边界缺陷——包括 offset-table 越界，以及 four-stream Huffman 在极小 regenerated size 下第四段"
        "计算下溢、令前序段越过 literal buffer 的内存安全漏洞（并补了 sanitizer 回归）。这些正是 hidden 套件"
        "考察的长尾，最终 hidden 37/37。"),
}


def _automation_recovers_insight(task: str, arm: str, partial, plain_partial, note: str) -> tuple:
    tail = f" {note}" if note else ""
    return ("automation_recovers_over_baseline",
            (f"{arm}（automation/续跑模式）在 {task} 达终态 partial={partial}，而同任务的 plain 基线"
             f"（有效运行）停在 partial={plain_partial}。gap≈{round((partial or 0) - (plain_partial or 0), 3)}"
             f"。这是同模型配置和时限预算下的单次观察，不能排除采样差异；"
             f"轨迹与继续验证补齐边界的机制假设一致。{tail}"),
            ("这条正面回答“automation 如何帮基线做出题”：其价值在于**抵消模型的早停**——当基线在"
             "public/可见信号变绿后就宣布完成时，续跑循环继续驱动它覆盖 hidden 边界。注意这只在"
             "**基线尚有未覆盖长尾**时有增益；在 plain 已达上限的任务上（本套多数任务）automation 与"
             "基线打平，不产生此类 gap。"),
            ("在更多任务和重复运行上量化‘早停’的普遍度（如对比各模式 agent step 数与最终 hidden 覆盖），"
             "并确认基线低分是能力所限还是早停所致；对早停敏感的任务优先用续跑模式。"),
            "expected", "medium")


_AUTOMATION_ARMS = {"goal", "heartbeat"}
_RECOVER_MIN_GAP = 0.2


def _insight_for(task: str, arm: str, cell: dict, cols: dict, benchmark_id: str) -> dict | None:
    """只为**有明确洞见**的 case 生成 draft 记录（否则返回 None）。

    cols 是该任务所有模式的列，用来取 plain 基线做 automation-recovers 对照。
    """
    partial = cell.get("partial")
    reward = cell.get("reward")
    build_failed = bool(cell.get("build_failed"))
    unblock = cell.get("unblock") or 0
    cont = cell.get("cont") or 0
    status = cell.get("status")

    # plain 基线只取**有效**运行做对照：partial==0 视为退化/不可比的基线（未产出可度量的
    # 能力结果），用 >0 过滤掉，避免把这类零分格算成 automation 的增益，保证 gap 是真实的
    # 能力差而非基线缺失。
    plain_partial = (cols.get("plain") or {}).get("partial")
    plain_valid = isinstance(plain_partial, (int, float)) and plain_partial > 0

    if build_failed:
        (fc, causal, impl, probe, exp, conf) = _build_failed_insight(task, arm)
    elif status != _COMPLETE and unblock >= 5:
        # 对保留组使用相同机制条件，不作跨已撤回组的归因。
        (fc, causal, impl, probe, exp, conf) = _idle_churn_insight(
            task, arm, unblock, cont, partial)
    elif (arm in _AUTOMATION_ARMS and status == _COMPLETE
          and (reward == 1 or (partial or 0) >= _STABLE_MIN)
          and plain_valid and (partial or 0) - plain_partial >= _RECOVER_MIN_GAP):
        # automation 模式完成且明显高于**有效** plain 基线 → 真正的“automation 帮基线”正例。
        note = _GOOD_CASE_NOTES.get((task, arm), "")
        (fc, causal, impl, probe, exp, conf) = _automation_recovers_insight(
            task, arm, partial, plain_partial, note)
    else:
        return None

    rid = _run_id(cell.get("run_dir", ""), task, arm)
    return {
        "schema_version": SCHEMA,
        "benchmark_id": benchmark_id,
        "study_id": STUDY_ID,
        "case_id": task,
        "run_id": rid,
        "outcome_status": _outcome_status(cell),
        "failure_class": fc,
        "causal_summary": _clip(causal),
        "expectedness": exp,
        "implication": _clip(impl),
        "next_probe": _clip(probe),
        "confidence": conf,
        # 只放 case+arm+attempt 哈希句柄（无 stamp / 无 raw 路径）；具体 run 目录属私有证据。
        "evidence_refs": [f"run:{rid}"],
        "privacy_classification": "public_safe",
        "producer_redaction_attested": True,
    }


# Cross-arm behavior aggregates are withdrawn; no retained-arm-only recomputation is available.
_STUDY_OBSERVATIONS = []


def build(data: dict) -> list[dict]:
    # benchmark_id 取 data.json 自带的 `bench`，不再硬编码（口径随数据走）。
    benchmark_id = data.get("bench") or "swe-marathon"
    out = []
    for task, cols in data.get("cells", {}).items():
        for arm, cell in cols.items():
            if arm not in PUBLIC_ARMS or not isinstance(cell, dict):
                continue
            rec = _insight_for(task, arm, cell, cols, benchmark_id)
            if rec:
                out.append(rec)
    out.sort(key=lambda r: (r["case_id"], r["run_id"]))
    return out


def _payload(records: list[dict]) -> dict:
    return {
        "note": ("Non-official DRAFT case-insight records for the codex×LoopX SWE-Marathon "
                 "study. Two tiers: per-case `records` (child of a single terminal run) and "
                 "`study_observations` (cross-task aggregate on how LoopX continuation changes "
                 "behavior). Field shapes track benchmark_case_insight_projection_v0 (upstream "
                 "#3878 / RFC #3812) so records can be promoted, but schema_version is a draft: "
                 "these are NOT attachable via the official benchmark provider until matching "
                 "benchmark_experiment_board_row_v0 rows exist (see README lineage). Identity "
                 "note: data.json is latest-attempt-per-(task,arm) after _common.collect() "
                 "folding; run_id hashes the surviving attempt's run_dir."),
        "schema_version": SCHEMA,
        "promotion_target": OFFICIAL_SCHEMA,
        "study_observations": _STUDY_OBSERVATIONS,
        "count": len(records),
        "records": records,
    }


def main() -> int:
    # 固定读写脚本所属 benchmark 目录下的 data.json / case_insights.json，不从 argv 取
    # 路径——避免把用户可控参数拼进文件路径（S2083）。用法：`python3 case_insights.py`。
    records = build(json.loads((_BASE / "data.json").read_text()))
    outp = _BASE / "case_insights.json"
    outp.write_text(json.dumps(_payload(records), ensure_ascii=False, indent=2))
    print(f"写出 {outp}：{len(records)} 条 draft case-insight + {len(_STUDY_OBSERVATIONS)} 条 study 观测")
    for r in records:
        print(f"  {r['case_id']:26} {r['failure_class']:34} "
              f"outcome={r['outcome_status']:13} exp={r['expectedness']:10} conf={r['confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
