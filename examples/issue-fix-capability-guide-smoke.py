#!/usr/bin/env python3
"""Smoke-test the bilingual public issue-fix capability entry surface."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGLISH_GUIDE = ROOT / "docs/capabilities/issue-fix/README.md"
CHINESE_GUIDE = ROOT / "docs/capabilities/issue-fix/README.zh-CN.md"
CAPABILITY_INDEX = ROOT / "docs/capabilities/README.md"
ENGLISH_README = ROOT / "README.md"
CHINESE_README = ROOT / "README.zh-CN.md"
REVIEWER_PROTOCOL = (
    ROOT
    / "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-recommendation-v0.md"
)
REVIEWER_REQUEST_PROTOCOL = (
    ROOT
    / "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-request-v0.md"
)
REVIEWER_NOTIFICATION_SINK_PROTOCOL = (
    ROOT
    / "docs/capabilities/issue-fix/protocols/issue-fix-reviewer-notification-sinks-v0.md"
)

PRIVATE_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def assert_public_safe(text: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        assert not pattern.search(text), pattern.pattern


def assert_markers(text: str, markers: tuple[str, ...]) -> None:
    for marker in markers:
        assert marker in text, marker


def main() -> int:
    english = ENGLISH_GUIDE.read_text(encoding="utf-8")
    chinese = CHINESE_GUIDE.read_text(encoding="utf-8")
    capability_index = CAPABILITY_INDEX.read_text(encoding="utf-8")
    english_readme = ENGLISH_README.read_text(encoding="utf-8")
    chinese_readme = CHINESE_README.read_text(encoding="utf-8")
    reviewer_protocol = REVIEWER_PROTOCOL.read_text(encoding="utf-8")
    reviewer_request_protocol = REVIEWER_REQUEST_PROTOCOL.read_text(encoding="utf-8")
    reviewer_notification_sink_protocol = REVIEWER_NOTIFICATION_SINK_PROTOCOL.read_text(
        encoding="utf-8"
    )

    assert english.startswith("# Issue-Fix Capability")
    assert chinese.startswith("# Issue-Fix 能力")
    assert "[中文](README.zh-CN.md)" in english
    assert "[English](README.md)" in chinese
    assert "[issue-fix](issue-fix/README.md)" in capability_index
    assert "[中文](issue-fix/README.zh-CN.md)" in capability_index
    assert "docs/capabilities/issue-fix/README.md" in english_readme
    assert "docs/capabilities/issue-fix/README.zh-CN.md" in chinese_readme

    shared_markers = (
        "issue_fix_repository_context_input_v0",
        "fix_pr",
        "comment_only",
        "triage_only",
        "loopx issue-fix reviewer-plan",
        "loopx issue-fix reviewer-request",
        "CODEOWNERS",
        "continuous_monitor",
        "runnable_successor",
        "https://github.com/volcengine/OpenViking/issues/3102",
        "https://github.com/volcengine/OpenViking/pull/3115",
        "https://github.com/volcengine/OpenViking/pull/3121",
        "https://github.com/volcengine/OpenViking/pull/3148",
        "https://github.com/huangruiteng/loopx/pull/1784",
        "https://github.com/huangruiteng/loopx/pull/1883",
        "https://github.com/huangruiteng/loopx/pull/1887",
        "resume_when=pr_merged:#123",
        "pr_merge",
        "issue_fix_reusable_knowledge_input_v0",
        "memory_verified_decision_influence",
        "python3 examples/issue-fix-reviewer-recommendation-smoke.py",
        "python3 examples/issue-fix-reviewer-request-smoke.py",
        "--notification-sinks-json",
        "python3 examples/issue-fix-reviewer-notification-sink-smoke.py",
    )
    assert_markers(english, shared_markers)
    assert_markers(chinese, shared_markers)
    assert_markers(
        english,
        (
            "## Product Position",
            "## What LoopX Provides Underneath",
            "Durable goal state",
            "Kanban/status projection",
            "Quota and scheduler policy",
            "Authority and interaction gates",
            "## End-To-End Design",
            "## Implemented Surfaces",
            "## Reviewer Routing Contract",
            "## Human Interaction Model",
            "## Roadmap",
            "## Success Metrics",
            "## Conversational `/loopx` Entry",
            "concrete blocker",
            "structured no-follow-up",
            "permission-only comment fallback",
            "avoid duplicates",
            "project-dedicated",
            "## Public OpenViking Usage And Evidence",
            "Event-backed wait and resume",
            "Merge-triggered resume",
        ),
    )
    assert_markers(
        chinese,
        (
            "## 产品定位",
            "## LoopX 底座提供什么",
            "持久化 goal state",
            "Kanban/status 投影",
            "Quota 与 scheduler policy",
            "Authority 与 interaction gate",
            "## 端到端设计",
            "## 已实现能力面",
            "## Reviewer 路由 Contract",
            "## 人机交互模型",
            "## Roadmap",
            "## 成功指标",
            "## 对话式 `/loopx` 入口",
            "具体 blocker",
            "结构化 no-follow-up",
            "权限不足 comment fallback",
            "不会重复 comment",
            "项目专属",
            "## OpenViking 的公开用法与 Pilot 证据",
            "事件驱动的 wait/resume",
            "Merge 后自动恢复",
        ),
    )
    assert reviewer_protocol.startswith("# issue_fix_reviewer_recommendation_v0")
    assert_markers(
        reviewer_protocol,
        (
            "repository's first supported `CODEOWNERS`",
            "changed path",
            "nearest module directory",
            "recommendation is not assignment",
            "automatic_review_request_allowed: true",
            "request_top_requestable_when_authorized",
            "review_request_performed: false",
            "python3 examples/issue-fix-reviewer-recommendation-smoke.py",
        ),
    )
    assert reviewer_request_protocol.startswith("# issue_fix_reviewer_request_v0")
    assert_markers(
        reviewer_request_protocol,
        (
            "request_top_requestable_when_authorized",
            "exclude the PR author",
            "external_review_request",
            "post-write verification",
            "permission-only comment fallback",
            "issue_fix_reviewer_comment_fallback_verified",
            "python3 examples/issue-fix-reviewer-request-smoke.py",
        ),
    )
    assert reviewer_notification_sink_protocol.startswith(
        "# issue_fix_reviewer_notification_sinks_v0"
    )
    assert_markers(
        reviewer_notification_sink_protocol,
        (
            "reader/user binding",
            "sender/bot binding",
            "config_pointer_registered",
            "auto-materializes",
            "local capability packet",
            "lark_bot_group_access_required",
            "private_destination_captured",
            "python3 examples/issue-fix-reviewer-notification-sink-smoke.py",
        ),
    )

    for text in (
        english,
        chinese,
        capability_index,
        english_readme,
        chinese_readme,
        reviewer_protocol,
        reviewer_request_protocol,
        reviewer_notification_sink_protocol,
    ):
        assert_public_safe(text)

    print("issue-fix-capability-guide-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
