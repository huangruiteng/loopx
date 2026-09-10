#!/usr/bin/env python3
"""case_insights.py 的回归测试。

产出的是**非官方 draft** 记录 `swe_marathon_case_insight_draft_v0`：字段形状对齐官方
`benchmark_case_insight_projection_v0`（upstream #3878 / RFC #3812）以便后续提升，但不
声称可进入 provider 生命周期（缺 board row）。

本地按 draft 规则逐项断言；另有一个 promotion 用例把记录 schema_version 提升为官方值、
交给**上游 normalizer** 校验（让上游成为字段形状的唯一真源），上游不可 import 时跳过。
可直接 `python3 test_case_insights.py`，也被仓库 pytest 收集。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import case_insights
from case_insights import (OFFICIAL_SCHEMA as _OFFICIAL, OUTCOMES as _OUTCOMES,
                           SCHEMA as _SCHEMA, _TEXT_LIMIT)

_EXPECT = {"expected", "unexpected", "mixed", "unknown"}
_CONF = {"low", "medium", "high"}
_ALLOWED = {
    "schema_version", "benchmark_id", "study_id", "case_id", "run_id", "outcome_status",
    "failure_class", "causal_summary", "expectedness", "implication", "next_probe",
    "confidence", "evidence_refs", "privacy_classification", "producer_redaction_attested",
}
_TOKENS = ("benchmark_id", "study_id", "case_id", "run_id", "failure_class")
_TEXTS = ("causal_summary", "implication", "next_probe")


def _assert_contract(p: dict) -> None:
    """逐项断言一条 draft 记录满足规则（每条 assert 单独一句，便于定位）。"""
    assert set(p) <= _ALLOWED
    assert p["schema_version"] == _SCHEMA
    assert p["privacy_classification"] == "public_safe"
    assert p["producer_redaction_attested"] is True
    assert p["expectedness"] in _EXPECT
    assert p["confidence"] in _CONF
    assert p["outcome_status"] in _OUTCOMES
    assert isinstance(p["evidence_refs"], list)
    assert len(p["evidence_refs"]) <= 16
    for ref in p["evidence_refs"]:
        assert isinstance(ref, str) and ref.strip()
        assert "\n" not in ref                      # 句柄不得内联 raw
    for field in _TOKENS:
        assert isinstance(p[field], str) and p[field].strip()
    for field in _TEXTS:
        assert isinstance(p[field], str)
        assert p[field].strip()                      # 非空
        assert len(p[field]) <= _TEXT_LIMIT


def _sample_data() -> dict:
    def cell(task, arm, **kw):
        base = {"task": task, "arm": arm, "reward": 0.0, "partial": 0.0,
                "build_failed": False, "status": "active", "cont": 0, "unblock": 0,
                "run_dir": f"{task}/{arm}/20260102-030405/{arm}"}
        base.update(kw)
        return base
    return {"bench": "swe-marathon", "cells": {
        "kubernetes-rust-rewrite": {
            "goal": cell("kubernetes-rust-rewrite", "goal",
                         build_failed=True, status="blocked", unblock=8, cont=10),
            "plain": cell("kubernetes-rust-rewrite", "plain",
                          partial=0.70, status="complete"),          # 有效基线
            "heartbeat": cell("kubernetes-rust-rewrite", "heartbeat",
                              reward=1.0, partial=1.0, status="complete", cont=9),
        },
        "zstd-decoder": {
            "goal": cell("zstd-decoder", "goal",
                         partial=0.60, status="blocked", unblock=8, cont=10),
        },
        "degenerate-zero-baseline": {  # plain=0.0 视为退化/不可比基线，不做对照
            "plain": cell("degenerate-zero-baseline", "plain", partial=0.0, status="complete"),
            "heartbeat": cell("degenerate-zero-baseline", "heartbeat",
                              reward=1.0, partial=1.0, status="complete", cont=3),
        },
        "excel-clone": {  # heartbeat 同形空转（P2-1：机制条件、arm-agnostic 应命中）
            "heartbeat": cell("excel-clone", "heartbeat",
                              partial=0.5, status="blocked", unblock=8, cont=9),
            "plain": cell("excel-clone", "plain", partial=0.49, status="active"),  # 无洞见 → skip
        },
        "withdrawn-arm": {
            "codex-cli": cell("withdrawn-arm", "codex-cli",
                              build_failed=True, status="blocked", unblock=8, cont=10),
        },
    }}


def test_records_conform_to_contract():
    recs = case_insights.build(_sample_data())
    assert recs
    for r in recs:
        _assert_contract(r)


def test_build_failure_and_idle_churn_detected():
    fclasses = {(r["case_id"], r["failure_class"]) for r in case_insights.build(_sample_data())}
    assert ("kubernetes-rust-rewrite", "build_failed_gate_zeroed") in fclasses
    assert ("zstd-decoder", "unattended_continuation_idle_churn") in fclasses


def test_idle_churn_is_arm_agnostic():
    """P2-1：公开保留模式使用同一机制条件（status≠complete 且 unblock≥5）。"""
    recs = case_insights.build(_sample_data())
    hb = next((r for r in recs if r["case_id"] == "excel-clone"
               and r["failure_class"] == "unattended_continuation_idle_churn"), None)
    assert hb is not None                            # heartbeat 的同形空转不能被 arm 名静默排除
    assert "arm" not in hb["implication"].lower() or "codex-cli" not in hb["implication"]


def test_automation_recovers_over_valid_baseline():
    """automation 模式完成且明显高于**有效** plain 基线 → 生成 automation_recovers 记录。"""
    recs = case_insights.build(_sample_data())
    ar = next((r for r in recs if r["case_id"] == "kubernetes-rust-rewrite"
               and r["failure_class"] == "automation_recovers_over_baseline"), None)
    assert ar is not None
    assert ar["outcome_status"] == "completed"


def test_no_recovery_credit_when_baseline_invalid():
    """plain==0.0 视为退化/不可比基线：不能把它说成 automation 的功劳。"""
    recs = case_insights.build(_sample_data())
    assert not any(r["case_id"] == "degenerate-zero-baseline"
                   and r["failure_class"] == "automation_recovers_over_baseline"
                   for r in recs)


def test_no_insight_case_is_skipped():
    recs = case_insights.build(_sample_data())
    assert not any(r["case_id"] == "excel-clone" and r["run_id"].startswith("excel-clone__plain")
                   for r in recs)


def test_build_failure_maps_to_runner_invalid():
    recs = case_insights.build(_sample_data())
    bf = next(r for r in recs if r["failure_class"] == "build_failed_gate_zeroed")
    assert bf["outcome_status"] == "runner_invalid"


def test_measured_blocked_is_incomplete_not_runner_invalid():
    """P2-3：有实测 partial 的 blocked 续跑（zstd-decoder/goal, partial=0.6）不能标
    runner_invalid（=无可计结果），否则与测量自相矛盾；应为 incomplete。"""
    recs = case_insights.build(_sample_data())
    zc = next(r for r in recs if r["case_id"] == "zstd-decoder"
              and r["failure_class"] == "unattended_continuation_idle_churn")
    assert zc["outcome_status"] == "incomplete"


def test_withdrawn_arms_are_excluded_from_public_records():
    """撤回的实验臂即使仍在历史输入里，也不能重新进入公开 case insights。"""
    recs = case_insights.build(_sample_data())
    assert not any(r["case_id"] == "withdrawn-arm" for r in recs)


def test_outcome_status_is_fail_closed():
    """P2-2：未知 status 必须抛错，不能像旧版一样静默归入 runner_invalid。"""
    try:
        case_insights._outcome_status({"status": "some-unknown-state"})
    except ValueError:
        return
    raise AssertionError("未知 status 未触发 fail-closed 抛错")


def test_active_status_maps_to_incomplete():
    """P2-2：status='active'（未 finalize）是 incomplete，不是 runner_invalid。"""
    assert case_insights._outcome_status({"status": "active", "partial": 0.8}) == "incomplete"


def test_run_id_is_exact_per_attempt():
    """B2 / P2-5：同 (task,arm) 的不同 run_dir（不同 attempt）必须得到不同 run_id，
    不再折叠成 task__arm；且句柄里不含原始时间戳。"""
    a = case_insights._run_id("t/arm/20260101-000000/arm", "t", "arm")
    b = case_insights._run_id("t/arm/20260102-999999/arm", "t", "arm")
    assert a != b
    assert "20260101-000000" not in a and "20260102-999999" not in b


def test_evidence_refs_carry_no_timestamp():
    for r in case_insights.build(_sample_data()):
        for ref in r["evidence_refs"]:
            assert "20260102-030405" not in ref     # 原始 stamp 不进公开句柄（哈希不含之）


def test_promoted_record_passes_upstream_normalizer():
    """P2-4：把一条**官方兼容 outcome**的 draft 记录提升为官方 schema，交给上游
    normalizer 校验——让上游成为字段形状唯一真源（能抓到如 case_id 含空格之类本地漏检的
    问题）。上游包不可 import 时跳过（本地 env 无 loopx 属正常）。draft 专有的 incomplete
    outcome 不在官方终态集内，故只提升 completed/runner_invalid 记录。"""
    try:
        from loopx.capabilities.benchmark_toolkit import study_projection as sp  # type: ignore
    except Exception:
        print("  SKIP promotion（上游 loopx 不可 import）")
        return
    normalizer = next((getattr(sp, n) for n in dir(sp)
                       if "normalize" in n.lower() and "case_insight" in n.lower()), None)
    if normalizer is None:
        print("  SKIP promotion（未找到 normalize_*case_insight* 函数）")
        return
    recs = [r for r in case_insights.build(_sample_data())
            if r["outcome_status"] in ("completed", "runner_invalid")]
    assert recs
    for r in recs:
        promoted = dict(r, schema_version=_OFFICIAL)
        normalizer(promoted)                         # 不抛即通过；上游拒绝会在此报错


def test_payload_writes_valid_file():
    # 直接构造 payload 写入临时目录（不经 argv/main 的路径逻辑）；tempfile 目录非
    # 用户可控，避免 case_insights.main() 固定写真实产物路径而在测试中覆盖它。
    recs = case_insights.build(_sample_data())
    payload = case_insights._payload(recs)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "ci.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        payload = json.loads(out.read_text())
        assert payload["schema_version"] == _SCHEMA
        assert payload["promotion_target"] == _OFFICIAL
        assert payload["count"] == len(payload["records"])
        for r in payload["records"]:
            _assert_contract(r)
        # #4193 撤回跨臂行为聚合；在完成保留臂重算前，不得复用旧结论。
        assert payload["study_observations"] == []


def _run() -> int:
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as exc:
                fails += 1
                print(f"  FAIL {name}: {exc}")
    print("OK" if not fails else f"{fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(_run())
