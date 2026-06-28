from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMAND = "/loopx-pr-review"
SCHEMA_VERSION = "loopx_pr_review_command_response_v0"

BOUNDARY = {
    "raw_logs_recorded": False,
    "raw_transcripts_recorded": False,
    "raw_connector_payloads_recorded": False,
    "credential_values_recorded": False,
    "absolute_paths_recorded": False,
    "private_source_bodies_recorded": False,
}

SOURCE_SURFACES = [
    "GitHub pull request metadata",
    "GitHub pull request body summary",
    "GitHub pull request changed-file list",
    "GitHub pull request status check rollup",
]

LOCAL_PATH_PATTERNS = (
    re.compile(r"/(?:Users|home|private|tmp|var)/[^\s`|,)]+"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\s`|,)]+"),
)

RUNTIME_OR_CLI_PREFIXES = (
    "src/",
    "lib/",
    "pkg/",
    "packages/",
    "cmd/",
    "internal/",
    "server/",
    "backend/",
    "app/",
    "apps/",
    "loopx/",
    "scripts/",
    "bin/",
    "tools/",
)

UI_PREFIXES = (
    "apps/dashboard/",
    "apps/web/",
    "apps/frontend/",
    "apps/site/",
    "web/",
    "frontend/",
    "ui/",
    "components/",
    "pages/",
    "views/",
    "public/",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_text(value: object, *, limit: int = 320) -> str:
    text = str(value or "").strip()
    for pattern in LOCAL_PATH_PATTERNS:
        text = pattern.sub("<local-path-redacted>", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "..."
    return text


def _join_short(items: list[str], *, limit: int = 3, fallback: str = "未提供") -> str:
    compact = [str(item).strip() for item in items if str(item).strip()]
    if not compact:
        return fallback
    return "、".join(compact[:limit])


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _run_gh_json(args: list[str], *, cwd: Path | None = None) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(proc.stdout or "null")


def resolve_current_github_repository(*, cwd: Path | None = None) -> str | None:
    try:
        payload = _run_gh_json(["repo", "view", "--json", "nameWithOwner"], cwd=cwd)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return str(payload.get("nameWithOwner") or "") or None


def _parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _github_search_date(value: object) -> str | None:
    parsed = _parse_timestamp(value)
    if parsed:
        return parsed.astimezone(timezone.utc).date().isoformat()
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None


def _pr_window_timestamp(pr: dict[str, Any]) -> datetime | None:
    return (
        _parse_timestamp(pr.get("mergedAt") or pr.get("merged_at"))
        or _parse_timestamp(pr.get("closedAt") or pr.get("closed_at"))
        or _parse_timestamp(pr.get("updatedAt") or pr.get("updated_at"))
    )


def _include_pr_in_window(pr: dict[str, Any], *, since: object | None) -> bool:
    since_dt = _parse_timestamp(since)
    if since_dt is None:
        return True
    activity_dt = _pr_window_timestamp(pr)
    return bool(activity_dt and activity_dt >= since_dt)


def normalize_pr_state_filter(value: object) -> str:
    state = str(value or "all").strip().lower()
    return state if state in {"open", "merged", "all"} else "all"


def fetch_github_pull_requests(
    *,
    repo: str | None,
    limit: int,
    cwd: Path | None = None,
    state_filter: str = "all",
    since: str | None = None,
) -> list[dict[str, Any]]:
    repo_args = ["--repo", repo] if repo else []
    normalized_state = normalize_pr_state_filter(state_filter)
    search_args: list[str] = []
    search_date = _github_search_date(since)
    if search_date:
        search_args = ["--search", f"updated:>={search_date}"]
    list_fields = [
        "number",
        "title",
        "url",
        "state",
        "isDraft",
        "reviewDecision",
        "mergeStateStatus",
        "headRefName",
        "baseRefName",
        "author",
        "updatedAt",
        "closedAt",
        "mergedAt",
        "mergeCommit",
        "body",
        "files",
        "changedFiles",
        "additions",
        "deletions",
        "statusCheckRollup",
    ]
    fetch_limit = max(1, limit)
    if since:
        fetch_limit = max(fetch_limit, min(100, fetch_limit * 3))
    rows = _run_gh_json(
        [
            "pr",
            "list",
            "--state",
            normalized_state,
            "--limit",
            str(fetch_limit),
            "--json",
            ",".join(list_fields),
            *search_args,
            *repo_args,
        ],
        cwd=cwd,
    )
    if not isinstance(rows, list):
        return []

    detailed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _include_pr_in_window(row, since=since):
            detailed.append(row)
    return detailed


def load_pr_fixture(path: Path) -> tuple[str | None, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return None, [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return None, []
    items = payload.get("pull_requests") or payload.get("prs") or []
    return (
        str(payload.get("repository") or "") or None,
        [item for item in _as_list(items) if isinstance(item, dict)],
    )


def _clean_body_lines(body: object) -> list[str]:
    lines: list[str] = []
    for raw in str(body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("<!--") or line.startswith("-->"):
            continue
        if line.startswith("#"):
            continue
        if line.startswith("- [") or line.startswith("* ["):
            continue
        if line.lower() in {"summary", "motivation", "changes", "testing"}:
            continue
        lines.append(line.strip("-* "))
    return lines


def _motivation(pr: dict[str, Any]) -> str:
    lines = _clean_body_lines(pr.get("body"))
    if lines:
        return _redact_text(" ".join(lines[:2]), limit=380)
    title = pr.get("title") or f"PR #{pr.get('number')}"
    return _redact_text(f"Review the intent described by the title: {title}", limit=220)


def _commit_headlines(pr: dict[str, Any], *, limit: int = 5) -> list[str]:
    commits: list[str] = []
    for item in _as_list(pr.get("commits")):
        if not isinstance(item, dict):
            continue
        headline = item.get("messageHeadline") or _as_dict(item.get("commit")).get("messageHeadline")
        if headline:
            commits.append(_redact_text(headline, limit=140))
        if len(commits) >= limit:
            break
    return commits


def _file_area(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    lowered = path.lower()
    if path in {
        "README.md",
        "README.zh-CN.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "LICENSE",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
    }:
        return "public_entry_or_policy"
    if path.startswith(".github/workflows/"):
        return "ci_or_release"
    if path.startswith("docs/"):
        return "public_docs"
    if path.startswith(("examples/", "fixtures/", "test/", "tests/", "spec/", "smoke/")):
        return "test_or_example"
    if path.startswith(UI_PREFIXES):
        return "app_or_ui_surface"
    if path.startswith(RUNTIME_OR_CLI_PREFIXES):
        return "product_runtime"
    if path.endswith((".toml", ".yaml", ".yml", ".json", ".ini")) or name in {
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "Makefile",
    }:
        return "build_or_config"
    if lowered.endswith((".md", ".mdx", ".rst")):
        return "public_docs"
    return "other"


def _files(pr: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for item in _as_list(pr.get("files")):
        if isinstance(item, str):
            path = item
            additions = None
            deletions = None
        elif isinstance(item, dict):
            path = str(item.get("path") or item.get("filename") or "")
            additions = item.get("additions")
            deletions = item.get("deletions")
        else:
            continue
        if not path:
            continue
        files.append(
            {
                "path": _redact_text(path, limit=180),
                "area": _file_area(path),
                "additions": additions,
                "deletions": deletions,
            }
        )
    return files


def _area_counts(files: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in files:
        area = str(item.get("area") or "other")
        counts[area] = counts.get(area, 0) + 1
    return counts


AREA_LABELS = {
    "public_entry_or_policy": "README/政策入口",
    "public_docs": "公开文档",
    "test_or_example": "smoke/示例",
    "app_or_ui_surface": "前端/展示面",
    "product_runtime": "运行时/CLI",
    "ci_or_release": "CI/发布",
    "build_or_config": "构建配置",
    "other": "其他文件",
}


RISK_LEVEL_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "unknown": "未知",
}


def _area_phrase(areas: dict[str, Any]) -> str:
    parts: list[str] = []
    for area, count in sorted(areas.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
        label = AREA_LABELS.get(str(area), str(area))
        parts.append(f"{label} {count}")
    return _join_short(parts, limit=4, fallback="未知区域")


def _top_file_phrase(files: list[dict[str, Any]], *, limit: int = 3) -> str:
    return _join_short([str(item.get("path") or "") for item in files if item.get("path")], limit=limit, fallback="未返回关键文件")


def _top_file_name_phrase(files: list[dict[str, Any]], *, limit: int = 2) -> str:
    names = [str(item.get("path") or "").rsplit("/", 1)[-1] for item in files if item.get("path")]
    return _join_short(names, limit=limit, fallback="关键文件")


def _int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _file_delta(item: dict[str, Any]) -> str:
    return f"+{_int_or_zero(item.get('additions'))}/-{_int_or_zero(item.get('deletions'))}"


def _file_churn(item: dict[str, Any]) -> int:
    return _int_or_zero(item.get("additions")) + _int_or_zero(item.get("deletions"))


def _area_change_intent(area: str) -> str:
    if area == "product_runtime":
        return "改变运行时、CLI 或控制面行为，属于最需要确认兼容性的改动。"
    if area == "app_or_ui_surface":
        return "改变用户可见页面或 dashboard/frontstage 展示，需要看真实浏览器效果。"
    if area == "public_entry_or_policy":
        return "改变 README、入口或贡献者政策，会影响新用户第一眼理解和仓库治理。"
    if area == "public_docs":
        return "沉淀公开说明、协议或使用路径，需要确认文档与实际 CLI/产品行为一致。"
    if area == "test_or_example":
        return "补充 smoke、fixture 或示例，把预期行为固定成可回归的验证面。"
    if area == "ci_or_release":
        return "改变 CI 或发布链路，风险主要在后续 PR 检查和发布稳定性。"
    if area == "build_or_config":
        return "改变构建、依赖或配置入口，需要确认安装、lint、测试命令仍可运行。"
    return "改变仓库其他辅助文件，需要结合 PR 动机判断是否属于必要范围。"


def _area_review_focus(area: str) -> str:
    if area == "product_runtime":
        return "重点看 JSON schema、默认行为、旧自动化兼容性和失败路径。"
    if area == "app_or_ui_surface":
        return "重点看首屏、状态可读性、响应式布局和公开/私有信息边界。"
    if area == "public_entry_or_policy":
        return "重点看第一屏承诺、CTA、安装路径和维护者规则是否准确。"
    if area == "public_docs":
        return "重点看命令示例、概念定义、用户路径和 shipped 行为是否一致。"
    if area == "test_or_example":
        return "重点看 smoke 是否覆盖 durable behavior，而不是过拟合临时文本。"
    if area == "ci_or_release":
        return "重点看 workflow 触发条件、权限、缓存和 required checks。"
    if area == "build_or_config":
        return "重点看依赖版本、入口脚本和跨环境可重复性。"
    return "重点看该文件是否应随本 PR 一起改，以及是否缺少对应验证。"


def _file_change_meaning(item: dict[str, Any]) -> str:
    path = str(item.get("path") or "")
    area = str(item.get("area") or "other")
    name = path.rsplit("/", 1)[-1]
    delta = _file_delta(item)
    if path == "loopx/pr_review.py":
        return f"`{name}` 是 PR-review packet 的核心生成逻辑，本次 {delta} 会直接改变用户看到的 review 队列内容。"
    if path.startswith("loopx/cli_commands/") or path == "loopx/cli.py":
        return f"`{name}` 改变 CLI 入口或参数/输出绑定，本次 {delta} 需要确认 slash command 和 shell 命令仍一致。"
    if path.startswith(("loopx/quota.py", "loopx/status.py", "loopx/todos.py", "loopx/todo_contract.py")):
        return f"`{name}` 属于控制面关键路径，本次 {delta} 可能影响 gate、todo、quota 或 status 投影。"
    if area == "test_or_example":
        return f"`{name}` 是验证或示例面，本次 {delta} 用来锁定行为预期，review 时要看断言是否真的覆盖产品合同。"
    if area == "public_docs":
        return f"`{name}` 是公开文档，本次 {delta} 主要改变用户/维护者理解路径，要检查命令和概念是否准确。"
    if area == "public_entry_or_policy":
        return f"`{name}` 是公开入口或政策文件，本次 {delta} 会影响新用户第一眼和维护者规则。"
    if area == "app_or_ui_surface":
        return f"`{name}` 是用户可见展示面，本次 {delta} 需要结合真实页面或截图确认体验。"
    if area == "ci_or_release":
        return f"`{name}` 是 CI/发布配置，本次 {delta} 需要确认 required checks 和权限没有倒退。"
    if area == "build_or_config":
        return f"`{name}` 是构建配置，本次 {delta} 需要确认安装、测试或打包路径稳定。"
    return f"`{name}` 本次 {delta}，需要确认它和 PR 动机属于同一 review 范围。"


def _detailed_change_analysis(item: dict[str, Any]) -> dict[str, Any]:
    scale = _as_dict(item.get("scale"))
    key_files = [file for file in _as_list(item.get("key_files")) if isinstance(file, dict)]
    ranked_files = sorted(key_files, key=_file_churn, reverse=True)
    areas = _as_dict(item.get("areas"))
    summary = _redact_text(
        f"这个 PR 的具体改动集中在{_area_phrase(areas)}，"
        f"总规模 {scale.get('changed_files', 0)} 个文件、+{scale.get('additions', 0)}/-{scale.get('deletions', 0)}。"
        f"建议先读 {_top_file_phrase(ranked_files, limit=3)}，确认最大 diff 是否兑现 PR 动机；"
        "再看 smoke/文档/检查结果是否能证明这些改动不会让 main 倒退。",
        limit=420,
    )
    area_breakdown: list[dict[str, Any]] = []
    for area, count in sorted(areas.items(), key=lambda pair: (-int(pair[1] or 0), str(pair[0]))):
        files = [file for file in ranked_files if str(file.get("area") or "other") == str(area)]
        area_breakdown.append(
            {
                "area": str(area),
                "label": AREA_LABELS.get(str(area), str(area)),
                "file_count": int(count or 0),
                "top_files": [str(file.get("path") or "") for file in files[:3]],
                "change_intent": _area_change_intent(str(area)),
                "review_focus": _area_review_focus(str(area)),
            }
        )
    file_walkthrough = [
        {
            "path": str(file.get("path") or ""),
            "area": str(file.get("area") or "other"),
            "delta": _file_delta(file),
            "meaning": _file_change_meaning(file),
            "review_focus": _area_review_focus(str(file.get("area") or "other")),
        }
        for file in ranked_files[:8]
    ]
    return {
        "schema_version": "pr_detailed_change_analysis_v0",
        "summary": summary,
        "area_breakdown": area_breakdown,
        "file_walkthrough": file_walkthrough,
        "review_order": [str(file.get("path") or "") for file in ranked_files[:5]],
    }


def _main_risk_phrase(main_risk: dict[str, Any]) -> str:
    level = str(main_risk.get("risk_level") or "unknown")
    regressions = [str(item) for item in _as_list(main_risk.get("potential_regressions")) if item]
    bug_risks = [str(item) for item in _as_list(main_risk.get("bug_risks")) if item]
    source = regressions[:1] or bug_risks[:1] or [str(main_risk.get("risk_summary") or "需人工确认主干影响")]
    return f"{level}，{_redact_text(source[0], limit=80)}"


def _check_phrase(checks: dict[str, Any]) -> str:
    failures = [str(item) for item in _as_list(checks.get("failures")) if item]
    pending = [str(item) for item in _as_list(checks.get("pending")) if item]
    if failures:
        return f"失败：{_join_short(failures, limit=2)}"
    if pending:
        return f"等待：{_join_short(pending, limit=2)}"
    return str(checks.get("summary") or "未返回检查结果")


def _check_brief_phrase(checks: dict[str, Any]) -> str:
    counts = _as_dict(checks.get("counts"))
    if checks.get("failures"):
        return f"{len(_as_list(checks.get('failures')))} fail"
    if checks.get("pending"):
        return f"{len(_as_list(checks.get('pending')))} pending"
    if counts.get("success"):
        return f"{counts.get('success')} pass"
    if int(checks.get("total") or 0) == 0:
        return "无 checks"
    return str(checks.get("summary") or "unknown")


def _guided_review_card(item: dict[str, Any]) -> dict[str, Any]:
    scale = _as_dict(item.get("scale"))
    checks = _as_dict(item.get("checks"))
    main_risk = _as_dict(item.get("main_regression_analysis"))
    motivation = _redact_text(item.get("motivation"), limit=90)
    short_motivation = _redact_text(item.get("motivation"), limit=50)
    key_files = [file for file in _as_list(item.get("key_files")) if isinstance(file, dict)]
    short_files = _top_file_name_phrase(key_files, limit=2)
    risk_level = str(main_risk.get("risk_level") or "unknown").lower()
    risk_label = RISK_LEVEL_LABELS.get(risk_level, risk_level)
    concrete_changes = (
        f"{_area_phrase(_as_dict(item.get('areas')))}；"
        f"{scale.get('changed_files', 0)} 个文件，+{scale.get('additions', 0)}/-{scale.get('deletions', 0)}；"
        f"重点看 {_top_file_phrase(key_files)}。"
    )
    risk = _main_risk_phrase(main_risk) if main_risk else "unknown，需人工确认主干影响"
    checks_summary = _check_phrase(checks)
    checks_brief = _check_brief_phrase(checks)
    first_prompt = "先判断 PR 是否应该存在，再确认改动范围、验证和主干风险是否对齐。"
    brief = _redact_text(
        f"动机：{short_motivation}。改动：{_area_phrase(_as_dict(item.get('areas')))}，"
        f"{scale.get('changed_files', 0)} 个文件 +{scale.get('additions', 0)}/-{scale.get('deletions', 0)}，"
        f"重点看 {short_files}。风险：{risk_label}；检查：{checks_brief}。"
        "Review：先看范围和验证是否对齐。",
        limit=200,
    )
    return {
        "schema_version": "guided_pr_review_card_v0",
        "brief": brief,
        "motivation": motivation,
        "concrete_changes": concrete_changes,
        "risk": risk,
        "checks": checks_summary,
        "review_prompt": first_prompt,
        "target_length": "100-200 Chinese characters when source metadata is compact",
    }


def _check_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("context") or item.get("workflowName") or "check")


def _check_state(item: dict[str, Any]) -> str:
    conclusion = str(item.get("conclusion") or "").upper()
    status = str(item.get("status") or "").upper()
    if conclusion in {"SUCCESS", "PASSED", "NEUTRAL", "SKIPPED"}:
        return "success"
    if conclusion in {"FAILURE", "FAILED", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "failure"
    if status in {"COMPLETED"} and conclusion:
        return conclusion.lower()
    if status in {"QUEUED", "IN_PROGRESS", "PENDING", "WAITING"}:
        return "pending"
    return "unknown"


def _checks(pr: dict[str, Any]) -> dict[str, Any]:
    items = [item for item in _as_list(pr.get("statusCheckRollup")) if isinstance(item, dict)]
    counts: dict[str, int] = {}
    failures: list[str] = []
    pending: list[str] = []
    for item in items:
        state = _check_state(item)
        counts[state] = counts.get(state, 0) + 1
        if state == "failure":
            failures.append(_redact_text(_check_name(item), limit=120))
        elif state == "pending":
            pending.append(_redact_text(_check_name(item), limit=120))
    if not items:
        return {
            "total": 0,
            "counts": {},
            "summary": "No status-check rollup was available from the source.",
            "failures": [],
            "pending": [],
        }
    if failures:
        summary = f"{len(failures)} failing check(s)."
    elif pending:
        summary = f"{len(pending)} pending check(s)."
    else:
        summary = f"{counts.get('success', 0)} successful check(s)."
    return {
        "total": len(items),
        "counts": counts,
        "summary": summary,
        "failures": failures[:5],
        "pending": pending[:5],
    }


def _risk_notes(pr: dict[str, Any], files: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    state = str(pr.get("state") or "").upper()
    if state == "MERGED" or pr.get("mergedAt") or pr.get("merged_at"):
        notes.append("Already merged: review for post-merge quality, regression risk, and follow-up work.")
    elif state in {"CLOSED"}:
        notes.append("Closed without a merge signal; review only if it still informs a replacement path.")
    if pr.get("isDraft"):
        notes.append("Draft PR: review may be advisory until it is marked ready.")
    if state != "MERGED" and str(pr.get("mergeStateStatus") or "").upper() not in {"", "CLEAN", "HAS_HOOKS", "UNKNOWN"}:
        notes.append(f"Merge state is {pr.get('mergeStateStatus')}; check conflict or branch-protection details.")
    if any(str(item.get("path") or "").startswith(RUNTIME_OR_CLI_PREFIXES) for item in files):
        notes.append("Touches runtime, app, CLI, or automation paths; review behavior and compatibility before merge.")
    changed = int(pr.get("changedFiles") or len(files) or 0)
    additions = int(pr.get("additions") or 0)
    deletions = int(pr.get("deletions") or 0)
    if changed >= 12 or additions + deletions >= 800:
        notes.append("Large review surface; split the review by area before approving.")
    checks = _checks(pr)
    if checks.get("failures"):
        notes.append("Failing status checks block a clean merge decision.")
    return notes


def _file_paths(files: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("path") or "") for item in files if item.get("path")]


def _matches_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _main_regression_analysis(pr: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    paths = _file_paths(files)
    areas = _area_counts(files)
    checks = _checks(pr)
    state = str(pr.get("state") or "").upper()
    changed = int(pr.get("changedFiles") or len(files) or 0)
    additions = int(pr.get("additions") or 0)
    deletions = int(pr.get("deletions") or 0)

    potential_regressions: list[str] = []
    bug_risks: list[str] = []
    verification_focus: list[str] = []

    if any(path.startswith(("loopx/quota.py", "loopx/status.py", "loopx/todos.py", "loopx/todo_contract.py")) for path in paths):
        potential_regressions.append(
            "Control-plane routing can regress: user gates, agent lane selection, monitor due projection, or quota spend/no-spend decisions may change on main."
        )
        bug_risks.append("A small projection mismatch can strand automation behind a wrong gate or hide runnable work.")
        verification_focus.append("Run focused quota/status/todo smokes and inspect one live quota/status packet after merge.")
    if any(path.startswith("loopx/cli_commands/") or path == "loopx/cli.py" for path in paths):
        potential_regressions.append(
            "CLI compatibility can regress: flags, JSON schema, markdown output, or shell-facing command examples may change for existing users."
        )
        bug_risks.append("Existing automation may parse older fields or rely on previous default command behavior.")
        verification_focus.append("Run the affected CLI smoke plus one live command against public-safe GitHub metadata or fixture data.")
    if any(path.startswith("loopx/benchmark_adapters/") or "skillsbench" in path.lower() or "terminal_bench" in path.lower() for path in paths):
        potential_regressions.append(
            "Benchmark launch or attribution behavior can regress: readiness blockers, attempt accounting, runner boundaries, or public/private evidence filtering may shift."
        )
        bug_risks.append("A benchmark helper change can misclassify a blocked launch as an attempted run, or expose raw benchmark evidence if boundaries slip.")
        verification_focus.append("Run the adapter's focused public smoke; avoid raw task text, trajectories, verifier output, and private logs.")
    if any(_matches_any(path, UI_PREFIXES) for path in paths):
        potential_regressions.append(
            "Frontstage/dashboard rendering can regress: routes, first viewport, responsive layout, hover affordances, or public-safe projection display may change."
        )
        bug_risks.append("A visual or routing change may look correct in fixture data but fail in the browser or hide important review context.")
        verification_focus.append("Run browser/frontstage smoke or capture the affected route when the first screen or interaction changes.")
    if any(path.startswith(".github/workflows/") or path.endswith(("pyproject.toml", "package.json", "uv.lock")) for path in paths):
        potential_regressions.append(
            "Build, install, or CI behavior can regress: dependency resolution, workflow triggers, or required checks may change for main."
        )
        bug_risks.append("A config-only diff can block future PR validation even when runtime code is unchanged.")
        verification_focus.append("Check workflow syntax or the smallest install/build command that exercises the changed config.")
    if areas and set(areas) <= {"public_docs", "test_or_example"}:
        potential_regressions.append(
            "Runtime regression risk is low, but public guidance or smoke expectations can drift from shipped behavior."
        )
        bug_risks.append("Docs-only or smoke-only changes can bless stale contracts if the example no longer matches the real CLI/runtime path.")
        verification_focus.append("Run `git diff --check` and the touched smoke; compare docs examples with current CLI help when command syntax is involved.")
    if not potential_regressions:
        potential_regressions.append("Main impact is localized to the touched files; verify the stated scope matches the diff before merge.")
        bug_risks.append("Unknown-area changes may still affect consumers if they alter shared data, examples, or public contracts.")
        verification_focus.append("Review changed files directly and run the narrowest smoke that exercises the touched surface.")

    if checks.get("failures"):
        bug_risks.append("Failing checks are present; merging would carry known red validation into main.")
    elif checks.get("pending"):
        bug_risks.append("Pending checks leave main-risk unresolved until they complete.")
    elif not checks.get("total"):
        bug_risks.append("No status-check rollup was available; rely on explicit local validation evidence before merge.")

    if changed >= 12 or additions + deletions >= 800:
        bug_risks.append("Large diff size increases reviewer miss risk; split by area or require stronger smoke coverage.")
        verification_focus.append("Review by area buckets and confirm each high-risk area has direct validation.")

    if state == "MERGED":
        verification_focus.append("Because this is already merged, prioritize post-merge canary, regression symptoms, and follow-up todos over merge readiness.")
    else:
        verification_focus.append("Before merge, confirm branch policy, conflict state, public/private boundary, and required checks.")

    high_area = (
        any(path.startswith(("loopx/quota.py", "loopx/status.py", "loopx/todos.py", "loopx/todo_contract.py")) for path in paths)
        or any(path.startswith("loopx/benchmark_adapters/") for path in paths)
        or bool(checks.get("failures"))
    )
    if high_area or changed >= 12 or additions + deletions >= 800:
        risk_level = "high"
    elif any(str(item.get("area")) in {"product_runtime", "app_or_ui_surface", "ci_or_release", "build_or_config"} for item in files):
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "schema_version": "main_regression_analysis_v0",
        "risk_level": risk_level,
        "risk_summary": _redact_text(
            f"{risk_level} main regression risk across {', '.join(sorted(areas)) or 'unknown'}; "
            f"{changed} file(s), +{additions}/-{deletions}."
        ),
        "potential_regressions": potential_regressions[:5],
        "bug_risks": bug_risks[:6],
        "verification_focus": verification_focus[:6],
        "post_merge_review": state == "MERGED",
    }


def _review_depth(files: list[dict[str, Any]]) -> str:
    areas = {str(item.get("area") or "") for item in files}
    if "product_runtime" in areas:
        return "runtime_behavior_review"
    if "app_or_ui_surface" in areas or "public_entry_or_policy" in areas:
        return "presentation_or_policy_review"
    if areas <= {"public_docs", "test_or_example"}:
        return "docs_and_smoke_review"
    return "standard_review"


def _parse_updated_epoch(value: object) -> float:
    parsed = _parse_timestamp(value)
    return parsed.timestamp() if parsed else 0.0


def _review_priority(pr: dict[str, Any], files: list[dict[str, Any]]) -> tuple[int, float]:
    is_draft = bool(pr.get("isDraft") or pr.get("is_draft"))
    review_decision = str(pr.get("reviewDecision") or pr.get("review_decision") or "").upper()
    state = str(pr.get("state") or "").upper()
    activity_at = (
        pr.get("mergedAt")
        or pr.get("merged_at")
        or pr.get("closedAt")
        or pr.get("closed_at")
        or pr.get("updatedAt")
        or pr.get("updated_at")
    )
    if is_draft:
        bucket = 4
    elif state == "MERGED":
        bucket = 3
    elif state == "CLOSED":
        bucket = 5
    elif review_decision in {"", "REVIEW_REQUIRED", "CHANGES_REQUESTED", "UNKNOWN"}:
        bucket = 0
    elif _review_depth(files) == "runtime_behavior_review":
        bucket = 1
    else:
        bucket = 2
    return (bucket, -_parse_updated_epoch(activity_at))


def _normalize_pr(pr: dict[str, Any]) -> dict[str, Any]:
    files = _files(pr)
    checks = _checks(pr)
    number = pr.get("number")
    url = pr.get("url") or (f"https://github.com/pull/{number}" if number else "")
    raw_state = str(pr.get("state") or "").upper()
    if not raw_state:
        raw_state = "MERGED" if pr.get("mergedAt") or pr.get("merged_at") else "OPEN"
    merge_commit = pr.get("mergeCommit") or pr.get("merge_commit")
    merge_commit_oid = _as_dict(merge_commit).get("oid") if isinstance(merge_commit, dict) else None
    item: dict[str, Any] = {
        "number": number,
        "title": _redact_text(pr.get("title"), limit=180),
        "url": _redact_text(url, limit=220),
        "state": raw_state,
        "author": _redact_text(_as_dict(pr.get("author")).get("login") or pr.get("author"), limit=80),
        "updated_at": pr.get("updatedAt"),
        "closed_at": pr.get("closedAt"),
        "merged_at": pr.get("mergedAt"),
        "merge_commit": _redact_text(merge_commit_oid, limit=80) if merge_commit_oid else None,
        "base_ref": _redact_text(pr.get("baseRefName"), limit=80),
        "head_ref": _redact_text(pr.get("headRefName"), limit=120),
        "is_draft": bool(pr.get("isDraft")),
        "review_decision": str(pr.get("reviewDecision") or "UNKNOWN"),
        "merge_state": str(pr.get("mergeStateStatus") or pr.get("mergeable") or "UNKNOWN"),
        "motivation": _motivation(pr),
        "scale": {
            "changed_files": int(pr.get("changedFiles") or len(files) or 0),
            "additions": int(pr.get("additions") or 0),
            "deletions": int(pr.get("deletions") or 0),
        },
        "areas": _area_counts(files),
        "key_files": files[:10],
        "commit_headlines": _commit_headlines(pr),
        "checks": checks,
        "review_depth": _review_depth(files),
        "risk_notes": _risk_notes(pr, files),
        "main_regression_analysis": _main_regression_analysis(pr, files),
        "review_prompts": [
            "What user or maintainer value does this PR unlock now?",
            "Do the touched files match that stated scope?",
            "Are validation evidence and risk boundaries strong enough for merge?",
            "What could regress on main, and which focused validation would catch it?",
        ],
        "evidence_commands": [
            f"gh pr view {number} --json title,body,files,commits,statusCheckRollup",
            f"gh pr diff {number} --stat",
        ]
        if number
        else [],
    }
    item["detailed_change_analysis"] = _detailed_change_analysis(item)
    item["guided_review_card"] = _guided_review_card(item)
    return item


def build_pr_review_packet(
    *,
    pull_requests: list[dict[str, Any]],
    repository: str | None,
    limit: int,
    source: str,
    state_filter: str = "all",
    since: str | None = None,
) -> dict[str, Any]:
    normalized_state_filter = normalize_pr_state_filter(state_filter)
    normalized_all = [_normalize_pr(item) for item in pull_requests]
    normalized_all = [
        item
        for item in normalized_all
        if (normalized_state_filter == "all" or str(item.get("state") or "").lower() == normalized_state_filter)
        and _include_pr_in_window(item, since=since)
    ]
    normalized_all.sort(key=lambda item: _review_priority(item, item.get("key_files") or []))
    normalized = normalized_all[: max(1, limit)]
    review_sequence = [
        {
            "rank": index,
            "number": item.get("number"),
            "title": item.get("title"),
            "url": item.get("url"),
            "state": item.get("state"),
            "review_depth": item.get("review_depth"),
            "main_risk_level": _as_dict(item.get("main_regression_analysis")).get("risk_level"),
            "why_now": _review_why_now(item),
        }
        for index, item in enumerate(normalized, start=1)
    ]
    open_review_required = [
        item
        for item in normalized
        if str(item.get("state") or "").upper() == "OPEN"
        and not item.get("is_draft")
        and str(item.get("review_decision") or "").upper() in {"", "REVIEW_REQUIRED", "CHANGES_REQUESTED", "UNKNOWN"}
    ]
    merged_items = [item for item in normalized if str(item.get("state") or "").upper() == "MERGED"]
    closed_items = [item for item in normalized if str(item.get("state") or "").upper() == "CLOSED"]
    first = review_sequence[0] if review_sequence else None
    review_attention_count = len(open_review_required) + len(merged_items)
    open_items = [item for item in normalized if str(item.get("state") or "").upper() == "OPEN"]
    headline = (
        (
            f"{len(normalized)} PR(s) in review window: "
            f"{len(open_items)} open, "
            f"{len(merged_items)} merged; {review_attention_count} need review attention."
        )
        if normalized
        else "No pull requests found for the requested review window."
    )
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "request": {
            "schema_version": "loopx_pr_review_command_request_v0",
            "command": COMMAND,
            "cli_command": "loopx pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]",
            "repository": repository,
            "limit": max(1, limit),
            "state_filter": normalized_state_filter,
            "since": since,
            "window": {
                "since": since,
                "state_filter": normalized_state_filter,
            },
            "source": source,
            "include": [
                "guided_review_card",
                "motivation",
                "detailed_change_analysis",
                "change_scope",
                "checks",
                "risk_notes",
                "main_regression_analysis",
                "review_sequence",
            ],
            "privacy_mode": "public_safe_github_metadata",
            "dry_run": True,
        },
        "generated_at": _now_iso(),
        "summary": {
            "headline": headline,
            "total_pr_count": len(normalized),
            "open_pr_count": len(open_items),
            "merged_pr_count": len(merged_items),
            "closed_pr_count": len(closed_items),
            "review_attention_count": review_attention_count,
            "open_review_attention_count": len(open_review_required),
            "post_merge_review_count": len(merged_items),
            "draft_count": sum(1 for item in normalized if item.get("is_draft")),
            "source_surfaces": SOURCE_SURFACES,
            "recommended_first_pr": first,
        },
        "review_sequence": review_sequence,
        "pull_requests": normalized,
        "actions": [
            {
                "action_id": "act_review_next_pr",
                "kind": "review",
                "requires_user_approval": False,
                "requires_primary_agent": False,
                "preview": "Start with the first PR in review_sequence, read its motivation, inspect key files, then decide approve/request changes/defer.",
            },
            {
                "action_id": "act_merge_after_review",
                "kind": "merge_or_publish",
                "requires_user_approval": False,
                "requires_primary_agent": True,
                "preview": "Merge only after repository policy, validation, and public/private boundary checks pass.",
            },
        ],
        "omissions": [
            "Raw logs, private connector payloads, credentials, local paths, and private source bodies were intentionally omitted.",
            "The command summarizes public PR metadata and does not post review comments, approve, merge, or spend quota.",
        ],
        "boundary": BOUNDARY,
    }


def _review_why_now(item: dict[str, Any]) -> str:
    state = str(item.get("state") or "").upper()
    if state == "MERGED":
        return "Merged in the review window; audit outcome, validation, and follow-up quality."
    if state == "CLOSED":
        return "Closed without a merge signal; check whether a replacement or cleanup is needed."
    if item.get("is_draft"):
        return "Draft PR; skim for early direction but do not treat as merge-ready."
    decision = str(item.get("review_decision") or "").upper()
    if decision in {"REVIEW_REQUIRED", "UNKNOWN", ""}:
        return "Open and awaiting reviewer decision."
    if decision == "CHANGES_REQUESTED":
        return "Changes were requested; verify whether the latest diff addresses them."
    if decision == "APPROVED":
        return "Approved but still open; check merge state and final validation."
    return "Open PR; confirm current merge readiness."


def render_pr_review_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "# Project PR Review Queue\n\n- ok: `False`\n- error: " + _redact_text(payload.get("error"))

    summary = _as_dict(payload.get("summary"))
    request = _as_dict(payload.get("request"))
    lines = [
        "# Project PR Review Queue",
        "",
        f"- command: `{request.get('command')}`",
        f"- repository: `{request.get('repository') or 'current gh repository'}`",
        f"- state_filter: `{request.get('state_filter') or 'all'}`",
        f"- since: `{request.get('since') or 'not set'}`",
        f"- headline: {summary.get('headline')}",
        f"- counts: total=`{summary.get('total_pr_count')}`, open=`{summary.get('open_pr_count')}`, merged=`{summary.get('merged_pr_count')}`, review_attention=`{summary.get('review_attention_count')}`, draft=`{summary.get('draft_count')}`",
        "",
        "## Review Sequence",
    ]
    sequence = [item for item in _as_list(payload.get("review_sequence")) if isinstance(item, dict)]
    if not sequence:
        lines.append("- none")
    for item in sequence:
        lines.append(
            f"{item.get('rank')}. [#{item.get('number')} {item.get('title')}]({item.get('url')}) "
            f"[{item.get('state')}] - "
            f"{item.get('review_depth')} / main_risk=`{item.get('main_risk_level')}`: {item.get('why_now')}"
        )

    for pr in [item for item in _as_list(payload.get("pull_requests")) if isinstance(item, dict)]:
        card = _as_dict(pr.get("guided_review_card"))
        lines.extend(
            [
                "",
                f"## PR #{pr.get('number')}: {pr.get('title')}",
                "",
                f"> {card.get('brief') or pr.get('motivation')}",
                "",
                f"- url: {pr.get('url')}",
                f"- state: `{pr.get('state')}`",
                f"- merged_at: `{pr.get('merged_at') or 'n/a'}`",
                f"- branch: `{pr.get('head_ref')}` -> `{pr.get('base_ref')}`",
                f"- status: review=`{pr.get('review_decision')}`, merge=`{pr.get('merge_state')}`, draft=`{pr.get('is_draft')}`",
                f"- 动机: {card.get('motivation') or pr.get('motivation')}",
                f"- 具体改动: {card.get('concrete_changes') or 'n/a'}",
                f"- 详细改动分析: {_as_dict(pr.get('detailed_change_analysis')).get('summary') or 'n/a'}",
                f"- 风险: {card.get('risk') or 'n/a'}",
                f"- 检查: {card.get('checks') or _as_dict(pr.get('checks')).get('summary')}",
                f"- Review prompt: {card.get('review_prompt') or '确认范围、验证和风险是否匹配。'}",
                f"- scale: files=`{_as_dict(pr.get('scale')).get('changed_files')}`, +`{_as_dict(pr.get('scale')).get('additions')}`, -`{_as_dict(pr.get('scale')).get('deletions')}`",
                f"- areas: `{json.dumps(pr.get('areas') or {}, ensure_ascii=False)}`",
            ]
        )
        commits = [item for item in _as_list(pr.get("commit_headlines")) if item]
        if commits:
            lines.append("- commits: " + "; ".join(f"`{item}`" for item in commits))
        key_files = [item for item in _as_list(pr.get("key_files")) if isinstance(item, dict)]
        if key_files:
            lines.append("- key files:")
            for item in key_files[:8]:
                lines.append(f"  - `{item.get('path')}` ({item.get('area')})")
        detailed = _as_dict(pr.get("detailed_change_analysis"))
        area_breakdown = [item for item in _as_list(detailed.get("area_breakdown")) if isinstance(item, dict)]
        if area_breakdown:
            lines.append("- 改动拆解:")
            for item in area_breakdown[:5]:
                top_files = _join_short([str(path) for path in _as_list(item.get("top_files"))], limit=3, fallback="无关键文件")
                lines.append(
                    f"  - {item.get('label')}（{item.get('file_count')} 个文件，{top_files}）："
                    f"{item.get('change_intent')} Review 重点：{item.get('review_focus')}"
                )
        walkthrough = [item for item in _as_list(detailed.get("file_walkthrough")) if isinstance(item, dict)]
        if walkthrough:
            lines.append("- 文件 walkthrough:")
            for item in walkthrough[:6]:
                lines.append(
                    f"  - `{item.get('path')}` {item.get('delta')}: "
                    f"{item.get('meaning')} Review 重点：{item.get('review_focus')}"
                )
        review_order = [str(item) for item in _as_list(detailed.get("review_order")) if item]
        if review_order:
            lines.append("- 推荐阅读顺序: " + " -> ".join(f"`{item}`" for item in review_order))
        risks = [item for item in _as_list(pr.get("risk_notes")) if item]
        lines.append("- risk notes: " + ("; ".join(str(item) for item in risks) if risks else "none"))
        main_risk = _as_dict(pr.get("main_regression_analysis"))
        if main_risk:
            lines.append(
                f"- main regression risk: `{main_risk.get('risk_level')}` - {main_risk.get('risk_summary')}"
            )
            regressions = [item for item in _as_list(main_risk.get("potential_regressions")) if item]
            if regressions:
                lines.append("- potential main regressions:")
                for item in regressions[:4]:
                    lines.append(f"  - {item}")
            bug_risks = [item for item in _as_list(main_risk.get("bug_risks")) if item]
            if bug_risks:
                lines.append("- bug risks:")
                for item in bug_risks[:4]:
                    lines.append(f"  - {item}")
            verification = [item for item in _as_list(main_risk.get("verification_focus")) if item]
            if verification:
                lines.append("- verification focus:")
                for item in verification[:4]:
                    lines.append(f"  - {item}")
        prompts = [item for item in _as_list(pr.get("review_prompts")) if item]
        if prompts:
            lines.append("- review prompts: " + " / ".join(str(item) for item in prompts))

    lines.extend(["", "## Boundary", "- Public PR metadata only; raw/private material is omitted."])
    return "\n".join(lines)
