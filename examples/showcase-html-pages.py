#!/usr/bin/env python3
"""Generate public-safe LoopX showcase HTML pages from the catalog."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "docs" / "showcases" / "showcase-catalog.json"
SHOWCASE_DIR = REPO_ROOT / "docs" / "showcases"
CASES_DIR = SHOWCASE_DIR / "cases"

PRIMARY_CASE_ORDER = [
    "2026-06-27-overnight-pr-batch",
    "2026-06-24-pr-issue-auto-fix",
    "2026-06-23-agent-to-agent-pr-comments",
    "2026-06-23-overnight-project-refactor",
    "2026-06-19-dynamic-workflow-hardware-agent",
    "2026-06-19-loopx-self-iteration",
    "2026-06-17-blocked-p0-safe-rotation",
]

FALLBACK_SHOWCASE_TABLE = {
    "2026-06-27-overnight-pr-batch": {
        "proof_point": "High-throughput multi-lane work can stay PR-sized, reviewable, and merge-safe.",
        "loopx_intervention": "todo claim, review packet, self-merge boundary, focused smoke, public-boundary scan",
    },
    "2026-06-24-pr-issue-auto-fix": {
        "proof_point": "Issue and review feedback can become a controlled executable repair loop.",
        "loopx_intervention": "issue-fix workflow, command pack, repro smoke, PR review feedback",
    },
    "2026-06-23-agent-to-agent-pr-comments": {
        "proof_point": "Agent lanes can coordinate around PR comments without losing owner review.",
        "loopx_intervention": "claimed_by, handoff gate, review packet, comment/fix loop",
    },
    "2026-06-23-overnight-project-refactor": {
        "proof_point": "Unattended refactors can split into human-sized PR slices instead of one large diff.",
        "loopx_intervention": "loop, todo follow-up, supersede, PR-sized slices",
    },
    "2026-06-19-dynamic-workflow-hardware-agent": {
        "proof_point": "Fuzzy multi-worker engineering goals can converge under one shared control plane.",
        "loopx_intervention": "goal state, worker handoff, dynamic workflow",
    },
    "2026-06-19-loopx-self-iteration": {
        "proof_point": "A high-churn multi-lane agent repo can keep state, evidence, and boundaries coherent.",
        "loopx_intervention": "todo, quota, gate, evidence, review packet, frontstage",
    },
    "2026-06-17-blocked-p0-safe-rotation": {
        "proof_point": "A blocked P0 decision should not stall safe P1/P2 work.",
        "loopx_intervention": "concrete user todo, safe fallback, quota control",
    },
}

DEFAULT_FRONTEND_CARDS = {
    "2026-06-27-overnight-pr-batch": {
        "visual_metaphor": "parallel PR lanes converge into a reviewable public merge rail",
        "story_beats": [
            "A long overnight window is split into PR-sized public repository slices.",
            "Each lane records validation, review boundary, and merge evidence.",
            "LoopX keeps throughput visible without hiding reviewer control.",
        ],
        "badges": ["PR batch", "review packet", "public boundary"],
    },
    "2026-06-24-pr-issue-auto-fix": {
        "visual_metaphor": "issue feedback turns into a closed repair loop with smoke evidence",
        "story_beats": [
            "A reviewer or issue report becomes a concrete repair target.",
            "LoopX preserves the repro path, fix scope, and validation command.",
            "The PR returns with a focused evidence packet instead of loose chat context.",
        ],
        "badges": ["issue fix", "repro smoke", "PR review"],
    },
    "2026-06-23-agent-to-agent-pr-comments": {
        "visual_metaphor": "agent comments hand off through ownership rather than scattered threads",
        "story_beats": [
            "One agent leaves actionable PR feedback with public-safe context.",
            "Another lane claims the follow-up and turns it into a bounded fix.",
            "The owner still sees the handoff, evidence, and residual review gate.",
        ],
        "badges": ["handoff", "PR comment", "claimed_by"],
    },
    "2026-06-23-overnight-project-refactor": {
        "visual_metaphor": "a large refactor travels as a sequence of small reviewable packets",
        "story_beats": [
            "Open-ended cleanup is reduced into ordered slices.",
            "Superseded or migrated work stays traceable through todo evidence.",
            "The result remains reviewable even when progress happens unattended.",
        ],
        "badges": ["refactor", "PR slices", "todo evidence"],
    },
}

ZH_CASE_COPY = {
    "2026-06-27-overnight-pr-batch": {
        "title": "一晚 PR 批次的可审阅控制",
        "headline": "一次长时间 LoopX 运行可以产出多条 PR-sized slice，同时让 review、验证和公开证据边界始终可见。",
        "proof_point": "高吞吐多 lane 工作也可以保持 PR 粒度、可审阅、可合并。",
        "loopx_intervention": "todo claim、review packet、自合并边界、focused smoke、公开边界扫描",
        "visual_metaphor": "多条 PR lane 汇入一条可审阅的公开合并轨道",
        "story_beats": [
            "一整晚的开放工作被切成适合 review 的公开仓库 PR slice。",
            "每条 lane 都记录验证、review 边界和合并证据。",
            "LoopX 让吞吐量可见，同时不抹掉 reviewer 的控制权。",
        ],
        "loopx_behavior": [
            "把大批量候选工作拆成可命名、可验证、可回滚的 PR 单元",
            "每条 lane 写回验证证据和 review 边界",
            "在公开仓库历史中保留可追溯的合并结果",
        ],
        "evidence_boundary": "只使用公开 Git 历史、PR 元数据和公开安全摘要；不提交内部状态、原始聊天、私有截图或本地运行证据。",
    },
    "2026-06-24-pr-issue-auto-fix": {
        "title": "PR Issue 自动修复循环",
        "headline": "review 反馈应该进入有 repro、修复、验证和 reviewer handoff 的有序修复 workflow。",
        "proof_point": "Issue 和 review 反馈可以变成受控、可执行的修复循环。",
        "loopx_intervention": "issue-fix workflow、command pack、repro smoke、PR review feedback",
        "visual_metaphor": "issue 反馈被闭环成带 smoke 证据的修复轨道",
        "story_beats": [
            "reviewer 或 issue 报告先变成一个具体修复目标。",
            "LoopX 保存 repro 路径、修复范围和验证命令。",
            "PR 回来时带着聚焦证据，而不是散落在聊天里的上下文。",
        ],
        "loopx_behavior": [
            "把 review comment 映射成可 claim 的修复 todo",
            "保留 repro、fix、validation 三段证据",
            "把剩余风险交还给 reviewer，而不是默认吞掉",
        ],
        "evidence_boundary": "公开页面只描述可复用的 issue-fix 模式和公开安全验证；不包含私有 issue 内容、内部 reviewer 语境或本地日志。",
    },
    "2026-06-23-agent-to-agent-pr-comments": {
        "title": "Agent-to-agent PR 评论与修复循环",
        "headline": "PR review 反馈可以成为有 owner 的 agent todo 和修复证据，而不是一条松散的聊天提醒。",
        "proof_point": "多条 agent lane 可以围绕 PR comment 协作，同时保留 owner review。",
        "loopx_intervention": "claimed_by、handoff gate、review packet、comment/fix loop",
        "visual_metaphor": "agent 评论通过 ownership 交接，而不是散落在线程里",
        "story_beats": [
            "一个 agent 留下带公开安全上下文的可执行 PR 反馈。",
            "另一条 lane claim 后续工作，并把它变成有边界的修复。",
            "owner 仍然能看到 handoff、证据和剩余 review gate。",
        ],
        "loopx_behavior": [
            "用 claimed_by 把 PR comment 变成明确责任",
            "把修复证据写回 review packet",
            "保留 owner handoff，不让 agent 之间互相默认放行",
        ],
        "evidence_boundary": "公开页面只展示 agent handoff 的模式；不暴露私有评论、内部 reviewer 名单、原始截图或本地状态。",
    },
    "2026-06-23-overnight-project-refactor": {
        "title": "一晚上自主重构项目",
        "headline": "广泛重构可以在夜间推进，但输出仍然要拆成适合人类 review 的小单元。",
        "proof_point": "无人值守的 refactor 可以拆成 PR-sized slice，而不是一个难审的大 diff。",
        "loopx_intervention": "loop、todo follow-up、supersede、PR-sized slices",
        "visual_metaphor": "大型 refactor 沿着一串小型 review packet 前进",
        "story_beats": [
            "开放式 cleanup 先被降解为有顺序的 slice。",
            "被 supersede 或迁移的工作通过 todo 证据保持可追踪。",
            "即使进展发生在夜间，结果仍然保持可审阅。",
        ],
        "loopx_behavior": [
            "把大范围 refactor 收敛成多个可验证 patch",
            "用 supersede 记录替换和迁移关系",
            "每个 slice 都留下下一步和剩余风险",
        ],
        "evidence_boundary": "公开页面只保留 refactor 控制面模式；不提交内部计划、私有状态叙事或原始运行轨迹。",
    },
    "2026-06-19-dynamic-workflow-hardware-agent": {
        "title": "动态 workflow：硬件 Agent 开发",
        "headline": "当多个 worker agent 参与一个模糊的长跑工程目标时，需要共享控制面来保持收敛。",
        "proof_point": "模糊的多 worker 工程目标可以在同一个共享控制面下收敛。",
        "loopx_intervention": "goal state、worker handoff、dynamic workflow",
        "visual_metaphor": "多条 worker lane 汇入同一个共享控制面",
        "story_beats": [
            "LoopX 持有 goal state、quota、todo、claim、evidence 和 history。",
            "Claude Code 在这个契约下编写任务级 orchestration script。",
            "hardware-agent worker 执行有边界的 RTL、simulation 和 validation 工作。",
            "五个公开 case 展示 closed task、DSE、旗舰 Fmax 优化和收敛下限。",
        ],
        "loopx_behavior": [
            "把 durable goal state 放在任意单个聊天线程之外",
            "显式管理 ownership、quota 和 evidence writeback",
            "只有在有边界验证后才允许脚本生成的 worker loop 继续",
            "向 operator 投影收敛状态和 human gate",
        ],
        "evidence_boundary": "公开安全交互 artifact；不包含原始聊天、截图、专有设计细节、私有仓库、本地路径、task id、凭据或未发布硬件 artifact。",
    },
    "2026-06-19-loopx-self-iteration": {
        "title": "LoopX Meta Agent 自迭代",
        "headline": "在 benchmark、产品、文档、planning 和 side-agent 多线并行时，高 churn 的 LoopX repo 仍然保持可读。",
        "proof_point": "高 churn 多 lane agent repo 可以保持状态、证据和边界一致。",
        "loopx_intervention": "todo、quota、gate、evidence、review packet、frontstage",
        "visual_metaphor": "自迭代 repo 通过 todo、quota 和 evidence rail 保持清醒",
        "story_beats": [
            "多条 lane 同时推进 benchmark、产品能力、文档和规划。",
            "LoopX 把 user gate、agent claim 和验证证据投影到同一控制面。",
            "公开 Git 历史提供工作量信号，私有运行细节留在边界外。",
        ],
        "loopx_behavior": [
            "用公共 Git 证据表达长期自迭代工作量",
            "用 todo 和 run history 维持 lane 间可追踪性",
            "把 efficiency model 写成可审阅而非夸张的产品叙事",
        ],
        "evidence_boundary": "只使用公开仓库历史和公开安全叙事；不包含内部目标状态、原始 heartbeat、私有计划或本地运行数据。",
    },
    "2026-06-17-blocked-p0-safe-rotation": {
        "title": "P0 阻塞后的 P1/P2 安全推进",
        "headline": "当 P0 lane 等待人类决策时，如果存在安全 fallback 工作，整个长跑目标不应该停住。",
        "proof_point": "被阻塞的 P0 决策不应该阻止安全的 P1/P2 工作继续。",
        "loopx_intervention": "concrete user todo、safe fallback、quota control",
        "visual_metaphor": "P0 gate 留在前台，安全 side path 继续推进",
        "story_beats": [
            "P0 决策被投影成具体 user todo，而不是笼统 owner gate。",
            "LoopX 在安全范围内继续 P1/P2 候选工作。",
            "quota 和 evidence writeback 限制无人值守工作的节奏。",
        ],
        "loopx_behavior": [
            "区分必须等人的 P0 和可验证的安全后续工作",
            "在 status/should-run contract 中保留 concrete gate",
            "只在有安全候选和验证边界时继续推进",
        ],
        "evidence_boundary": "使用合成 demo 证明控制面行为；不依赖真实私有阻塞事项、内部任务正文或本地运行状态。",
    },
    "2026-06-20-creator-operator-case-spec": {
        "title": "创作者-运营者长跑 Agent 案例",
        "headline": "创作者-运营者需要一种长跑 agent loop：研究可以继续，发布决策仍然 gated。",
        "proof_point": "创作与运营工作可以共享一个 gate-aware 的长期 agent loop。",
        "loopx_intervention": "creator-operator workflow、user gate、feedback capture、material library",
        "visual_metaphor": "研究 side path 继续积累素材，发布 gate 保持在人类手里",
        "story_beats": [
            "素材整理和研究探索可以作为安全 side path 继续。",
            "发布、外发或品牌判断仍然停在 owner gate。",
            "反馈契约把用户体验沉淀成可复用材料库。",
        ],
        "loopx_behavior": [
            "把创作准备和发布决策拆成不同风险层级",
            "在 gate 后继续安全的材料整理和反馈归档",
            "用假数据 storyboard 保护真实用户上下文",
        ],
        "evidence_boundary": "这是 synthetic product case spec；不代表真实私有用户故事，也不包含内部素材、客户信息或未授权截图。",
    },
}

UI = {
    "en": {
        "html_lang": "en",
        "language_label": "中文",
        "cases_nav": "Cases",
        "readme_nav": "README",
        "catalog_nav": "Catalog",
        "story": "Story",
        "boundary": "Boundary",
        "proof_title": "What This Case Proves",
        "proof_point": "Proof point",
        "loopx_intervention": "LoopX intervention",
        "hardware_anchors": "Public hardware anchors",
        "behavior": "Control-Plane Behavior",
        "story_beats": "Story Beats",
        "evidence_boundary": "Evidence Boundary",
        "narrative_note": "Narrative note",
        "storyboard": "Storyboard",
        "feedback_contract": "Feedback contract",
        "footer_case": "Public-safe showcase page generated from docs/showcases/showcase-catalog.json.",
        "gallery_eyebrow": "LoopX Showcase Gallery",
        "gallery_title": "Agent work that stays reviewable.",
        "gallery_copy": "Seven public-safe cases show how LoopX keeps long-running agent work tied to todos, gates, quota, handoffs, validation, review packets, and evidence boundaries.",
        "browse_cases": "Browse cases",
        "open_catalog": "Open catalog",
        "control_steps": [
            ("01 Goal", "Open-ended work becomes durable project state."),
            ("02 Todo", "Each lane has ownership, priority, and a bounded next move."),
            ("03 Gate", "Human decisions stay visible without stopping safe work."),
            ("04 Evidence", "Reviewable output links back to validation and public boundaries."),
        ],
        "showcase_cases": "Showcase Cases",
        "section_lede": "The order mirrors the current Showcase & Good Case packet: high-throughput proof first, then issue-fix, agent-to-agent collaboration, overnight refactor, dynamic hardware workflow, LoopX self-iteration, and blocked-P0 fallback.",
        "search_placeholder": "Search cases, patterns, or LoopX interventions",
        "public_cases": "public cases",
        "appendix_surface": "Appendix Surface",
        "appendix_lede": "Appendix material keeps product direction visible without mixing synthetic or private-adjacent evidence into the seven public proof cases.",
        "public_boundary": "Public Boundary",
        "public_boundary_copy": "These pages are generated from the public showcase catalog. They do not embed private documents, internal screenshots, raw chats, local active-state bodies, credentials, raw benchmark traces, or internal Lark media URLs.",
        "footer_index": "Generated from docs/showcases/showcase-catalog.json. Public case pages are copied into the GitHub Pages frontstage bundle.",
        "graph_operator": "operator + agent lane",
        "graph_trigger": "trigger",
        "graph_result": "public result",
        "graph_control": "todo / quota / evidence",
        "index_graph_catalog": "showcase catalog",
        "index_graph_proof": "proof point",
        "index_graph_control": "LoopX control",
        "index_graph_case": "case page",
    },
    "zh": {
        "html_lang": "zh-CN",
        "language_label": "English",
        "cases_nav": "案例",
        "readme_nav": "README",
        "catalog_nav": "Catalog",
        "story": "故事",
        "boundary": "边界",
        "proof_title": "这个案例证明了什么",
        "proof_point": "证明点",
        "loopx_intervention": "LoopX 介入",
        "hardware_anchors": "公开硬件锚点",
        "behavior": "控制面行为",
        "story_beats": "故事节奏",
        "evidence_boundary": "证据边界",
        "narrative_note": "叙事说明",
        "storyboard": "Storyboard",
        "feedback_contract": "反馈契约",
        "footer_case": "公开安全 showcase 页面，由 docs/showcases/showcase-catalog.json 生成。",
        "gallery_eyebrow": "LoopX Showcase Gallery",
        "gallery_title": "让 Agent 工作保持可审阅。",
        "gallery_copy": "七个公开安全案例展示 LoopX 如何把长跑 agent 工作绑定到 todo、gate、quota、handoff、验证、review packet 和证据边界。",
        "browse_cases": "浏览案例",
        "open_catalog": "打开 catalog",
        "control_steps": [
            ("01 Goal", "开放目标沉淀为 durable project state。"),
            ("02 Todo", "每条 lane 都有 owner、优先级和有边界的下一步。"),
            ("03 Gate", "人类决策保持可见，同时不阻塞安全工作。"),
            ("04 Evidence", "可审阅输出回链到验证和公开边界。"),
        ],
        "showcase_cases": "Showcase 案例",
        "section_lede": "顺序对齐当前 Showcase & Good Case packet：高吞吐证明、issue fix、agent-to-agent 协作、夜间重构、硬件动态 workflow、LoopX 自迭代和 P0 阻塞 fallback。",
        "search_placeholder": "搜索案例、模式或 LoopX 介入",
        "public_cases": "个公开案例",
        "appendix_surface": "附录案例",
        "appendix_lede": "附录材料保留产品方向，但不把 synthetic 或接近私有边界的证据混入七个公开证明案例。",
        "public_boundary": "公开边界",
        "public_boundary_copy": "这些页面由公开 showcase catalog 生成，不嵌入私有文档、内部截图、原始聊天、本地 active-state、凭据、原始 benchmark trace 或内部文档图片链接。",
        "footer_index": "由 docs/showcases/showcase-catalog.json 生成。公开 case 页面会被复制进 GitHub Pages frontstage bundle。",
        "graph_operator": "operator + agent lane",
        "graph_trigger": "触发",
        "graph_result": "公开结果",
        "graph_control": "todo / quota / evidence",
        "index_graph_catalog": "showcase catalog",
        "index_graph_proof": "证明点",
        "index_graph_control": "LoopX 控制面",
        "index_graph_case": "case 页面",
    },
}

HARDWARE_PUBLIC_ANCHORS = [
    "Claude Code",
    "DUDU",
    "CV32E40P",
    "VeeR EH1",
    "Viterbi",
]

STATUS_LABELS = {
    "public_evidence_case": "Public evidence",
    "public_safe_interactive_case": "Interactive case",
    "public_safe_pattern_case": "Pattern case",
    "public_safe_case_spec": "Case spec",
    "reproducible_synthetic_demo": "Reproducible demo",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def slug(value: object) -> str:
    safe = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return safe or "case"


def rel_href(source: Path, target: Path) -> str:
    return os.path.relpath(target, source.parent).replace(os.sep, "/")


def repo_path(path: str) -> Path:
    return (REPO_ROOT / path).resolve()


def ui(lang: str, key: str) -> Any:
    return UI[lang][key]


def case_copy(case: dict[str, Any], lang: str) -> dict[str, Any]:
    if lang == "zh":
        return ZH_CASE_COPY.get(str(case.get("id")), {})
    return {}


def localized(case: dict[str, Any], lang: str, key: str) -> str:
    copy = case_copy(case, lang)
    value = copy.get(key)
    if value is None:
        value = case.get(key)
    return str(value or "")


def localized_list(case: dict[str, Any], lang: str, key: str, fallback: Any) -> list[str]:
    copy = case_copy(case, lang)
    value = copy.get(key)
    if value is None:
        value = fallback
    return first_items(value, 8)


def case_html_path(case: dict[str, Any], lang: str = "zh") -> Path:
    interactive_page = case.get("interactive_page")
    if lang == "zh" and isinstance(interactive_page, str) and interactive_page:
        return repo_path(interactive_page)
    case_page = str(case.get("case_page") or "")
    if case_page.endswith(".md"):
        base = repo_path(case_page[:-3] + ".html")
    else:
        base = CASES_DIR / f"{slug(case.get('id') or case.get('title'))}.html"
    if lang == "en":
        return base.with_name(f"{base.stem}.en{base.suffix}")
    return base


def case_table(case: dict[str, Any], lang: str = "en") -> dict[str, str]:
    copy = case_copy(case, lang)
    if lang == "zh" and copy:
        return {
            "proof_point": str(copy.get("proof_point") or ""),
            "loopx_intervention": str(copy.get("loopx_intervention") or ""),
        }
    table = case.get("showcase_table")
    if isinstance(table, dict):
        return {
            "proof_point": str(table.get("proof_point") or ""),
            "loopx_intervention": str(table.get("loopx_intervention") or ""),
        }
    return FALLBACK_SHOWCASE_TABLE.get(str(case.get("id")), {
        "proof_point": str(case.get("headline") or ""),
        "loopx_intervention": ", ".join(str(value) for value in case.get("pattern_tags", [])[:4]),
    })


def ordered_cases(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {str(case.get("id")): case for case in cases}
    primary = [by_id[case_id] for case_id in PRIMARY_CASE_ORDER if case_id in by_id]
    primary_ids = {str(case.get("id")) for case in primary}
    appendix = [case for case in cases if str(case.get("id")) not in primary_ids]
    return primary, appendix


def first_items(values: Any, limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values[:limit]]


def badges(values: list[str]) -> str:
    return "".join(f"<span>{esc(value)}</span>" for value in values)


ZH_STATUS_LABELS = {
    "public_evidence_case": "公开证据",
    "public_safe_interactive_case": "交互案例",
    "public_safe_pattern_case": "模式案例",
    "public_safe_case_spec": "案例规格",
    "reproducible_synthetic_demo": "可复现 demo",
}


def status_label(case: dict[str, Any], lang: str = "en") -> str:
    status = str(case.get("status") or "case")
    if lang == "zh":
        return ZH_STATUS_LABELS.get(status, status.replace("_", " "))
    return STATUS_LABELS.get(status, status.replace("_", " ").title())


def metric_cards(case: dict[str, Any]) -> str:
    workload = case.get("workload_signal")
    if not isinstance(workload, dict):
        return ""

    cards: list[tuple[str, str]] = []
    public_git = workload.get("public_git") if isinstance(workload.get("public_git"), dict) else {}
    whole = workload.get("whole_repository") if isinstance(workload.get("whole_repository"), dict) else {}
    public_window = workload.get("public_window") if isinstance(workload.get("public_window"), dict) else {}
    window = workload.get("window") if isinstance(workload.get("window"), dict) else {}
    efficiency = workload.get("efficiency_model") if isinstance(workload.get("efficiency_model"), dict) else {}

    if public_git.get("merged_commits") is not None:
        cards.append((str(public_git["merged_commits"]), "merged commits"))
    if public_git.get("files_touched") is not None:
        cards.append((str(public_git["files_touched"]), "files touched"))
    if window.get("hours") is not None:
        cards.append((f"{window['hours']}h", "public Git window"))
    if whole.get("commit_count") is not None:
        cards.append((str(whole["commit_count"]), "public commits"))
    if public_window.get("calendar_days") is not None:
        cards.append((f"{public_window['calendar_days']}d", "Git window"))
    estimated = efficiency.get("estimated_developer_days")
    if isinstance(estimated, dict) and estimated.get("low") and estimated.get("high"):
        cards.append((f"{estimated['low']}-{estimated['high']}d", "baseline estimate"))
    compression = efficiency.get("single_engineer_calendar_compression")
    if isinstance(compression, dict) and compression.get("low") and compression.get("high"):
        cards.append((f"{compression['low']}-{compression['high']}x", "calendar compression"))

    if not cards:
        return ""
    return "".join(
        f'<div class="metric"><strong>{esc(value)}</strong><span>{esc(label)}</span></div>'
        for value, label in cards[:4]
    )


def behavior_items(case: dict[str, Any], lang: str) -> str:
    items = localized_list(case, lang, "loopx_behavior", case.get("loopx_behavior"))
    return "".join(f"<li>{esc(item)}</li>" for item in items[:6])


def beat_items(case: dict[str, Any], lang: str) -> str:
    frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
    beats = localized_list(case, lang, "story_beats", frontend.get("story_beats"))
    if not beats:
        beats = localized_list(case, lang, "loopx_behavior", case.get("loopx_behavior"))[:5]
    return "".join(
        f'<li><span>{index:02d}</span><p>{esc(beat)}</p></li>'
        for index, beat in enumerate(beats, start=1)
    )


def case_links(case: dict[str, Any], *, current: Path, lang: str) -> str:
    links: list[str] = []
    case_page = case.get("case_page")
    if isinstance(case_page, str) and case_page:
        links.append(
            f'<a class="link-button secondary" href="{esc(rel_href(current, repo_path(case_page)))}">{esc(ui(lang, "narrative_note"))}</a>'
        )
    demo = case.get("demo_command")
    if isinstance(demo, str) and demo:
        links.append(f'<code class="demo-command">{esc(demo)}</code>')
    storyboard = case.get("storyboard_path")
    if isinstance(storyboard, str) and storyboard:
        links.append(
            f'<a class="link-button secondary" href="{esc(rel_href(current, repo_path(storyboard)))}">{esc(ui(lang, "storyboard"))}</a>'
        )
    feedback = case.get("feedback_contract_path")
    if isinstance(feedback, str) and feedback:
        links.append(
            f'<a class="link-button secondary" href="{esc(rel_href(current, repo_path(feedback)))}">{esc(ui(lang, "feedback_contract"))}</a>'
        )
    return "\n".join(links)


def control_graph(case: dict[str, Any], lang: str) -> str:
    frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
    metaphor = localized(case, lang, "visual_metaphor") or str(frontend.get("visual_metaphor") or "agent lanes converge through one shared control plane")
    table = case_table(case, lang)
    center = table["loopx_intervention"].split(",")[0].strip() or "LoopX control plane"
    left = str(case.get("domain") or "goal")
    right = status_label(case, lang)
    return f"""
    <figure class="control-graph" aria-label="LoopX control-plane diagram">
      <svg viewBox="0 0 920 520" role="img">
        <title>{esc(case.get("title") or "LoopX showcase diagram")}</title>
        <rect x="0" y="0" width="920" height="520" rx="8" class="graph-bg" />
        <path d="M460 96 L460 150" class="line muted" />
        <rect x="333" y="42" width="254" height="58" rx="8" class="node node-accent" />
        <text x="460" y="77" text-anchor="middle" class="node-label">{esc(ui(lang, "graph_operator"))}</text>
        <rect x="72" y="170" width="215" height="96" rx="8" class="node" />
        <text x="180" y="211" text-anchor="middle" class="node-label">{esc(left[:28])}</text>
        <text x="180" y="234" text-anchor="middle" class="node-sub">{esc(ui(lang, "graph_trigger"))}</text>
        <rect x="352" y="156" width="216" height="124" rx="8" class="node node-accent-fill" />
        <text x="460" y="204" text-anchor="middle" class="node-label">{esc(center[:30])}</text>
        <text x="460" y="229" text-anchor="middle" class="node-sub">{esc(ui(lang, "graph_control"))}</text>
        <rect x="632" y="170" width="215" height="96" rx="8" class="node" />
        <text x="740" y="211" text-anchor="middle" class="node-label">{esc(right[:28])}</text>
        <text x="740" y="234" text-anchor="middle" class="node-sub">{esc(ui(lang, "graph_result"))}</text>
        <path d="M287 218 L342 218" class="line accent" />
        <path d="M568 218 L622 218" class="line accent" />
        <path d="M740 266 L740 378 L180 378 L180 276" class="line return" />
        <circle cx="180" cy="378" r="5" class="dot" />
        <circle cx="740" cy="378" r="5" class="dot alt" />
        <rect x="206" y="326" width="508" height="44" rx="8" class="caption-box" />
        <text x="460" y="353" text-anchor="middle" class="caption">{esc(metaphor[:86])}</text>
      </svg>
    </figure>
    """


def page_css() -> str:
    return """
    :root {
      color-scheme: dark;
      --bg: #0b0b0c;
      --panel: #121318;
      --panel-2: #171920;
      --ink: #f4f2ee;
      --muted: #b7bbc7;
      --dim: #7f8492;
      --line: #343843;
      --line-2: #4a4f5e;
      --accent: #6e79d6;
      --accent-2: #7ed4a8;
      --accent-3: #e1b36a;
      --danger: #e07a7a;
      --max: 1180px;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    a { color: inherit; }
    .page-shell { min-height: 100vh; }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 5;
      border-bottom: 1px solid rgba(255,255,255,.08);
      background: rgba(11,11,12,.92);
      backdrop-filter: blur(12px);
    }
    .topbar-inner {
      max-width: var(--max);
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 22px;
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      font-weight: 720;
    }
    .brand-mark {
      width: 30px;
      height: 30px;
      border: 2px solid var(--accent);
      border-radius: 8px;
      display: inline-grid;
      place-items: center;
      color: var(--accent-2);
      font-size: 14px;
    }
    .topbar nav { display: flex; flex-wrap: wrap; gap: 10px; }
    .topbar nav a, .link-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      border: 1px solid var(--line-2);
      border-radius: 8px;
      padding: 8px 11px;
      text-decoration: none;
      color: var(--ink);
      font-size: 13px;
      font-weight: 650;
      background: rgba(255,255,255,.03);
    }
    .topbar nav a:hover, .link-button:hover { border-color: var(--accent); }
    .link-button.secondary { color: var(--muted); }
    main { max-width: var(--max); margin: 0 auto; padding: 38px 22px 70px; }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, .95fr) minmax(380px, 1.05fr);
      gap: 28px;
      align-items: center;
      min-height: min(720px, calc(100vh - 64px));
      padding-bottom: 26px;
    }
    .eyebrow {
      margin: 0 0 14px;
      color: var(--accent-2);
      font-size: 12px;
      font-weight: 750;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      max-width: 760px;
      font-size: clamp(44px, 7vw, 94px);
      line-height: .91;
      letter-spacing: 0;
    }
    .hero-copy {
      margin: 20px 0 0;
      max-width: 680px;
      color: var(--muted);
      font-size: clamp(16px, 2vw, 20px);
      line-height: 1.6;
    }
    .hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
    .hero-actions .primary {
      background: var(--ink);
      border-color: var(--ink);
      color: var(--bg);
    }
    .meta-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
    .pill, .badges span, .status-pill {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 5px 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      background: rgba(255,255,255,.03);
    }
    .status-pill { color: var(--accent-2); border-color: rgba(126,212,168,.45); }
    .control-graph {
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #0f1014;
      box-shadow: 0 18px 80px rgba(0,0,0,.28);
    }
    .control-graph svg { display: block; width: 100%; height: auto; }
    .graph-bg { fill: #0b0b0c; }
    .node { fill: none; stroke: #666b75; stroke-width: 3; }
    .node-accent { stroke: var(--accent); }
    .node-accent-fill { fill: rgba(110,121,214,.16); stroke: var(--accent); stroke-width: 3; }
    .node-label { fill: var(--ink); font-size: 18px; font-weight: 720; }
    .node-sub { fill: var(--dim); font-size: 13px; font-weight: 650; }
    .line { fill: none; stroke-width: 3; }
    .line.muted { stroke: #3a3d42; }
    .line.accent { stroke: var(--accent); }
    .line.return { stroke: #555b66; }
    .dot { fill: var(--accent); }
    .dot.alt { fill: var(--accent-3); }
    .caption-box { fill: rgba(255,255,255,.035); stroke: rgba(255,255,255,.08); }
    .caption { fill: var(--muted); font-size: 13px; font-weight: 650; }
    .section { border-top: 1px solid rgba(255,255,255,.08); padding: 34px 0; }
    .section h2 { margin: 0 0 18px; font-size: clamp(28px, 4vw, 46px); line-height: 1; }
    .section-lede { margin: -6px 0 24px; max-width: 760px; color: var(--muted); line-height: 1.65; }
    .metrics, .case-grid, .proof-grid, .link-grid {
      display: grid;
      gap: 12px;
    }
    .metrics { grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 18px; }
    .metric, .proof, .case-card, .boundary-panel, .behavior-panel, .timeline-panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    .metric { padding: 16px; }
    .metric strong { display: block; font-size: 28px; line-height: 1; color: var(--ink); }
    .metric span { display: block; margin-top: 8px; color: var(--dim); font-size: 12px; font-weight: 650; }
    .proof-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .proof { padding: 18px; }
    .proof span { color: var(--accent-2); font-size: 12px; font-weight: 780; text-transform: uppercase; }
    .proof p { margin: 10px 0 0; color: var(--muted); line-height: 1.6; }
    .case-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .case-card {
      display: grid;
      gap: 12px;
      min-height: 310px;
      padding: 18px;
      text-decoration: none;
      color: inherit;
    }
    .case-card:hover { border-color: var(--accent); }
    .case-card h3 { margin: 0; font-size: 23px; line-height: 1.08; }
    .case-card p { margin: 0; color: var(--muted); line-height: 1.55; }
    .case-card .badges { display: flex; flex-wrap: wrap; gap: 6px; align-self: end; }
    .case-card__meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .case-card__date { color: var(--dim); font-size: 12px; font-weight: 700; }
    .case-card__proof { border-left: 2px solid var(--accent); padding-left: 10px; font-size: 13px; color: var(--muted); }
    .page-layout { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 18px; align-items: start; }
    .behavior-panel, .timeline-panel, .boundary-panel { padding: 20px; }
    .behavior-panel h2, .timeline-panel h2, .boundary-panel h2 { font-size: 24px; }
    .behavior-list, .beat-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
    .behavior-list li {
      border-left: 2px solid var(--accent);
      padding: 7px 0 7px 12px;
      color: var(--muted);
      line-height: 1.55;
    }
    .beat-list li {
      display: grid;
      grid-template-columns: 42px minmax(0,1fr);
      gap: 10px;
      align-items: start;
      color: var(--muted);
    }
    .beat-list li span {
      display: inline-grid;
      place-items: center;
      width: 34px;
      height: 28px;
      border: 1px solid var(--line-2);
      border-radius: 8px;
      color: var(--accent-2);
      font-size: 12px;
      font-weight: 780;
    }
    .beat-list li p { margin: 2px 0 0; line-height: 1.55; }
    .boundary-panel { background: #121514; border-color: rgba(126,212,168,.22); }
    .boundary-panel p { margin: 0; color: var(--muted); line-height: 1.6; }
    .side-stack { display: grid; gap: 12px; align-content: start; }
    .demo-command {
      display: block;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--accent-2);
      background: #0d0f12;
      white-space: normal;
      overflow-wrap: anywhere;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .control-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 20px;
    }
    .control-strip div {
      min-height: 92px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--panel-2);
    }
    .control-strip span { color: var(--accent-3); font-size: 12px; font-weight: 760; }
    .control-strip p { margin: 8px 0 0; color: var(--muted); font-size: 13px; line-height: 1.45; }
    .search-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      margin-bottom: 18px;
    }
    .search-row input {
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0 12px;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
    }
    .search-row .count { align-self: center; color: var(--dim); font-size: 13px; font-weight: 650; }
    .public-note { color: var(--dim); font-size: 12px; line-height: 1.6; }
    footer { border-top: 1px solid rgba(255,255,255,.08); padding: 28px 22px 44px; color: var(--dim); }
    footer div { max-width: var(--max); margin: 0 auto; }
    @media (max-width: 940px) {
      .hero, .page-layout { grid-template-columns: 1fr; min-height: auto; }
      .metrics, .case-grid, .control-strip { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .proof-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 620px) {
      main { padding: 26px 14px 48px; }
      .topbar-inner { align-items: flex-start; flex-direction: column; padding: 12px 14px; }
      .metrics, .case-grid, .control-strip { grid-template-columns: 1fr; }
      .search-row { grid-template-columns: 1fr; }
      h1 { font-size: 44px; }
    }
    """


def html_head(title: str) -> str:
    return f"""<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <link rel="icon" href="data:,">
  <style>{page_css()}</style>
</head>"""


def index_path(lang: str) -> Path:
    if lang == "en":
        return SHOWCASE_DIR / "index.en.html"
    return SHOWCASE_DIR / "index.html"


def topbar(current: Path, lang: str, alternate: Path) -> str:
    index_href = rel_href(current, index_path(lang))
    readme_href = rel_href(current, SHOWCASE_DIR / "README.md")
    catalog_href = rel_href(current, CATALOG)
    alternate_href = rel_href(current, alternate)
    return f"""
    <header class="topbar">
      <div class="topbar-inner">
        <a class="brand" href="{esc(index_href)}"><span class="brand-mark">LX</span><span>LoopX Showcases</span></a>
        <nav aria-label="Showcase navigation">
          <a href="{esc(index_href)}#cases">{esc(ui(lang, "cases_nav"))}</a>
          <a href="{esc(readme_href)}">{esc(ui(lang, "readme_nav"))}</a>
          <a href="{esc(catalog_href)}">{esc(ui(lang, "catalog_nav"))}</a>
          <a href="{esc(alternate_href)}">{esc(ui(lang, "language_label"))}</a>
        </nav>
      </div>
    </header>
    """


def render_case_page(case: dict[str, Any], primary: bool, lang: str) -> str:
    output = case_html_path(case, lang)
    alternate = case_html_path(case, "en" if lang == "zh" else "zh")
    frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
    table = case_table(case, lang)
    tags = first_items(case.get("pattern_tags"), 5)
    badges_values = first_items(frontend.get("badges"), 5) or tags[:4]
    metrics = metric_cards(case)
    anchors = ""
    if str(case.get("id")) == "2026-06-19-dynamic-workflow-hardware-agent":
        anchor_text = (
            f"loopx 在芯片开发任务上的实践: {', '.join(HARDWARE_PUBLIC_ANCHORS)}"
            if lang == "zh"
            else ", ".join(HARDWARE_PUBLIC_ANCHORS)
        )
        anchors = (
            f'<div class="proof"><span>{esc(ui(lang, "hardware_anchors"))}</span>'
            f'<p>{esc(anchor_text)}</p></div>'
        )
    metric_markup = f'<div class="metrics">{metrics}</div>' if metrics else ""
    appendix_label = "" if primary else '<span class="pill">appendix</span>'
    links = case_links(case, current=output, lang=lang)
    title = localized(case, lang, "title")
    headline = localized(case, lang, "headline")
    evidence_boundary = localized(case, lang, "evidence_boundary")
    return f"""<!doctype html>
<html lang="{esc(ui(lang, "html_lang"))}">
{html_head("LoopX Showcase: " + title)}
<body>
  <div class="page-shell">
    {topbar(output, lang, alternate)}
    <main>
      <section class="hero">
        <div>
          <p class="eyebrow">{esc(case.get("date") or "")} / {esc(status_label(case, lang))}</p>
          <h1>{esc(title)}</h1>
          <p class="hero-copy">{esc(headline)}</p>
          <div class="meta-row">
            <span class="status-pill">{esc(case.get("domain") or "showcase")}</span>
            {appendix_label}
            {badges(badges_values)}
          </div>
          <div class="hero-actions">
            <a class="link-button primary" href="#story">{esc(ui(lang, "story"))}</a>
            <a class="link-button secondary" href="#boundary">{esc(ui(lang, "boundary"))}</a>
          </div>
        </div>
        {control_graph(case, lang)}
      </section>

      <section class="section" id="proof">
        <h2>{esc(ui(lang, "proof_title"))}</h2>
        <div class="proof-grid">
          <div class="proof"><span>{esc(ui(lang, "proof_point"))}</span><p>{esc(table["proof_point"])}</p></div>
          <div class="proof"><span>{esc(ui(lang, "loopx_intervention"))}</span><p>{esc(table["loopx_intervention"])}</p></div>
          {anchors}
        </div>
        {metric_markup}
      </section>

      <section class="section page-layout" id="story">
        <div class="behavior-panel">
          <h2>{esc(ui(lang, "behavior"))}</h2>
          <ol class="behavior-list">{behavior_items(case, lang)}</ol>
        </div>
        <aside class="side-stack">
          <div class="timeline-panel">
            <h2>{esc(ui(lang, "story_beats"))}</h2>
            <ol class="beat-list">{beat_items(case, lang)}</ol>
          </div>
          <div class="boundary-panel" id="boundary">
            <h2>{esc(ui(lang, "evidence_boundary"))}</h2>
            <p>{esc(evidence_boundary)}</p>
          </div>
          {links}
        </aside>
      </section>
    </main>
    <footer><div>{esc(ui(lang, "footer_case"))}</div></footer>
  </div>
</body>
</html>
"""


def render_index(cases: list[dict[str, Any]], lang: str) -> str:
    primary, appendix = ordered_cases(cases)
    current = index_path(lang)
    alternate = index_path("en" if lang == "zh" else "zh")
    cards = "\n".join(render_index_card(case, current=current, lang=lang) for case in primary)
    appendix_cards = "\n".join(render_index_card(case, current=current, lang=lang) for case in appendix)
    steps = "\n".join(
        f"<div><span>{esc(label)}</span><p>{esc(copy)}</p></div>"
        for label, copy in ui(lang, "control_steps")
    )
    initial_count = f'{len(primary)} {ui(lang, "public_cases")}' if lang == "en" else f'{len(primary)}{ui(lang, "public_cases")}'
    count_expression = "`${visible} public cases`" if lang == "en" else "`${visible}个公开案例`"
    return f"""<!doctype html>
<html lang="{esc(ui(lang, "html_lang"))}">
{html_head("LoopX Showcase Gallery")}
<body>
  <div class="page-shell">
    {topbar(current, lang, alternate)}
    <main>
      <section class="hero">
        <div>
          <p class="eyebrow">{esc(ui(lang, "gallery_eyebrow"))}</p>
          <h1>{esc(ui(lang, "gallery_title"))}</h1>
          <p class="hero-copy">{esc(ui(lang, "gallery_copy"))}</p>
          <div class="hero-actions">
            <a class="link-button primary" href="#cases">{esc(ui(lang, "browse_cases"))}</a>
            <a class="link-button secondary" href="{esc(rel_href(current, CATALOG))}">{esc(ui(lang, "open_catalog"))}</a>
          </div>
          <div class="control-strip" aria-label="LoopX showcase control loop">
            {steps}
          </div>
        </div>
        {index_graph(primary, lang)}
      </section>

      <section class="section" id="cases">
        <h2>{esc(ui(lang, "showcase_cases"))}</h2>
        <p class="section-lede">{esc(ui(lang, "section_lede"))}</p>
        <div class="search-row">
          <input id="case-search" type="search" placeholder="{esc(ui(lang, "search_placeholder"))}" aria-label="Search showcase cases">
          <span class="count" id="case-count">{esc(initial_count)}</span>
        </div>
        <div class="case-grid" data-case-grid>
          {cards}
        </div>
      </section>

      <section class="section">
        <h2>{esc(ui(lang, "appendix_surface"))}</h2>
        <p class="section-lede">{esc(ui(lang, "appendix_lede"))}</p>
        <div class="case-grid">
          {appendix_cards}
        </div>
      </section>

      <section class="section">
        <h2>{esc(ui(lang, "public_boundary"))}</h2>
        <div class="boundary-panel">
          <p>{esc(ui(lang, "public_boundary_copy"))}</p>
        </div>
      </section>
    </main>
    <footer><div>{esc(ui(lang, "footer_index"))}</div></footer>
  </div>
  <script>
    const input = document.getElementById('case-search');
    const count = document.getElementById('case-count');
    const cards = Array.from(document.querySelectorAll('[data-case-card]'));
    input.addEventListener('input', () => {{
      const query = input.value.trim().toLowerCase();
      let visible = 0;
      for (const card of cards) {{
        const match = !query || card.dataset.search.includes(query);
        card.style.display = match ? '' : 'none';
        if (match) visible += 1;
      }}
      count.textContent = {count_expression};
    }});
  </script>
</body>
</html>
"""


def render_index_card(case: dict[str, Any], *, current: Path, lang: str) -> str:
    output = case_html_path(case, lang)
    frontend = case.get("frontend_card") if isinstance(case.get("frontend_card"), dict) else {}
    table = case_table(case, lang)
    tags = first_items(case.get("pattern_tags"), 4)
    badge_values = first_items(frontend.get("badges"), 4) or tags
    title = localized(case, lang, "title")
    headline = localized(case, lang, "headline")
    search = " ".join(
        str(value)
        for value in [
            title,
            headline,
            case.get("domain"),
            case.get("status"),
            table.get("proof_point"),
            table.get("loopx_intervention"),
            *tags,
        ]
        if value
    ).lower()
    return f"""
      <a class="case-card" href="{esc(rel_href(current, output))}" data-case-card data-search="{esc(search)}">
        <div class="case-card__meta">
          <span class="status-pill">{esc(status_label(case, lang))}</span>
          <span class="case-card__date">{esc(case.get("date") or "")}</span>
        </div>
        <h3>{esc(title)}</h3>
        <p>{esc(headline)}</p>
        <p class="case-card__proof">{esc(table["proof_point"])}</p>
        <div class="badges">{badges(badge_values)}</div>
      </a>
    """


def index_graph(primary: list[dict[str, Any]], lang: str) -> str:
    labels = [str(case.get("date") or "") for case in primary[:7]]
    dots = "\n".join(
        f'<circle cx="{120 + index * 105}" cy="{310 + (index % 2) * 22}" r="7" class="dot{" alt" if index % 2 else ""}" />'
        f'<text x="{120 + index * 105}" y="{350 + (index % 2) * 22}" text-anchor="middle" class="node-sub">{esc(label[5:])}</text>'
        for index, label in enumerate(labels)
    )
    return f"""
    <figure class="control-graph" aria-label="Showcase case rail">
      <svg viewBox="0 0 920 520" role="img">
        <title>LoopX showcase gallery rail</title>
        <rect x="0" y="0" width="920" height="520" rx="8" class="graph-bg" />
        <rect x="150" y="70" width="620" height="76" rx="8" class="node node-accent" />
        <text x="460" y="115" text-anchor="middle" class="node-label">{esc(ui(lang, "index_graph_catalog"))}</text>
        <rect x="110" y="204" width="190" height="72" rx="8" class="node" />
        <text x="205" y="246" text-anchor="middle" class="node-label">{esc(ui(lang, "index_graph_proof"))}</text>
        <rect x="365" y="196" width="190" height="88" rx="8" class="node node-accent-fill" />
        <text x="460" y="235" text-anchor="middle" class="node-label">{esc(ui(lang, "index_graph_control"))}</text>
        <text x="460" y="257" text-anchor="middle" class="node-sub">todo / gate / evidence</text>
        <rect x="620" y="204" width="190" height="72" rx="8" class="node" />
        <text x="715" y="246" text-anchor="middle" class="node-label">{esc(ui(lang, "index_graph_case"))}</text>
        <path d="M300 240 L354 240" class="line accent" />
        <path d="M555 240 L610 240" class="line accent" />
        <path d="M120 310 C260 282 340 334 460 310 S660 282 780 310" class="line return" />
        {dots}
      </svg>
    </figure>
    """


def update_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    cases = catalog.get("cases")
    if not isinstance(cases, list):
        raise ValueError("catalog must contain cases")
    by_id = {str(case.get("id")): case for case in cases}
    reordered: list[dict[str, Any]] = []
    for case_id in PRIMARY_CASE_ORDER:
        if case_id in by_id:
            reordered.append(by_id.pop(case_id))
    reordered.extend(by_id.values())

    for rank, case in enumerate(reordered, start=1):
        zh_output = case_html_path(case, "zh")
        en_output = case_html_path(case, "en")
        zh_rel = zh_output.relative_to(REPO_ROOT).as_posix()
        en_rel = en_output.relative_to(REPO_ROOT).as_posix()
        case["interactive_page"] = zh_rel
        case["interactive_page_zh"] = zh_rel
        case["interactive_page_en"] = en_rel
        case["localized_pages"] = {"zh": zh_rel, "en": en_rel}
        if str(case.get("id")) in FALLBACK_SHOWCASE_TABLE:
            case["showcase_rank"] = rank
            case["showcase_table"] = FALLBACK_SHOWCASE_TABLE[str(case["id"])]
            if not isinstance(case.get("frontend_card"), dict):
                case["frontend_card"] = DEFAULT_FRONTEND_CARDS.get(str(case["id"]), {
                    "visual_metaphor": "a LoopX control-plane rail turns ambiguous agent work into reviewable evidence",
                    "story_beats": first_items(case.get("loopx_behavior"), 3),
                    "badges": first_items(case.get("pattern_tags"), 3),
                })
    catalog["cases"] = reordered
    return catalog


def read_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clean_generated_text(text), encoding="utf-8")


def clean_generated_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


def generate(*, write_files: bool) -> list[Path]:
    catalog = update_catalog(read_catalog())
    cases = catalog["cases"]
    primary, appendix = ordered_cases(cases)
    outputs: list[Path] = []
    if write_files:
        CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for case in primary + appendix:
        for lang in ("zh", "en"):
            output = case_html_path(case, lang)
            html_text = render_case_page(case, primary=case in primary, lang=lang)
            outputs.append(output)
            if write_files:
                write(output, html_text)
    for lang in ("zh", "en"):
        path = index_path(lang)
        outputs.append(path)
        if write_files:
            write(path, render_index(cases, lang))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed HTML/catalog match generated output.")
    args = parser.parse_args()

    if args.check:
        catalog = update_catalog(read_catalog())
        expected_catalog = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        actual_catalog = CATALOG.read_text(encoding="utf-8")
        if actual_catalog != expected_catalog:
            raise AssertionError("showcase catalog is not normalized; run examples/showcase-html-pages.py")
        cases = catalog["cases"]
        primary, appendix = ordered_cases(cases)
        for case in primary + appendix:
            for lang in ("zh", "en"):
                output = case_html_path(case, lang)
                expected = clean_generated_text(render_case_page(case, primary=case in primary, lang=lang))
                if output.read_text(encoding="utf-8") != expected:
                    raise AssertionError(f"{output} is not generated from the catalog")
        for lang in ("zh", "en"):
            path = index_path(lang)
            if path.read_text(encoding="utf-8") != clean_generated_text(render_index(cases, lang)):
                raise AssertionError(f"{path} is not generated from the catalog")
        print("showcase-html-pages check ok")
        return 0

    outputs = generate(write_files=True)
    for output in outputs:
        print(output.relative_to(REPO_ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
