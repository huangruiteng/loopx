from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable


LARK_DIGITAL_CLONE_SCAN_SCHEMA_VERSION = "loopx_lark_digital_clone_scan_v0"
LARK_DIGITAL_CLONE_TODO_PACKET_SCHEMA_VERSION = "loopx_lark_digital_clone_todo_packet_v0"
DEFAULT_OUT_DIR = Path(".local/lark-digital-clone/latest")
DEFAULT_STYLE = "中文，简洁直接，像工作消息"
DEFAULT_CLI_BIN = "lark-cli"


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str]], CommandResult]


def local_iso(dt: datetime) -> str:
    text = dt.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    return f"{text[:-2]}:{text[-2:]}"


def parse_since_to_hours(value: str) -> int:
    text = str(value or "").strip().lower()
    match = re.fullmatch(r"(\d+)\s*([hd])?", text)
    if not match:
        raise ValueError("--since must look like 24h or 7d")
    amount = int(match.group(1))
    unit = match.group(2) or "h"
    if amount <= 0:
        raise ValueError("--since must be positive")
    if unit == "d":
        return amount * 24
    return amount


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return text.strip("_") or "item"


def default_command_runner(argv: list[str]) -> CommandResult:
    completed = subprocess.run(argv, text=True, capture_output=True, check=False)
    return CommandResult(
        argv=argv,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def parse_json(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("=== Dry Run ==="):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else "{}"
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {"_parse_error": True, "raw_text": stripped[:4000]}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for item in value:
            yield from iter_dicts(item)


def first_text(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None:
            text = " ".join(str(value).split())
            if text:
                return text
    return ""


def decode_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        raw = value
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return " ".join(raw.split())
        return decode_content(parsed)
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("text", "title", "content", "message", "summary"):
            if key in value:
                text = decode_content(value.get(key))
                if text:
                    parts.append(text)
        if "zh_cn" in value:
            text = decode_content(value.get("zh_cn"))
            if text:
                parts.append(text)
        if not parts:
            for child in value.values():
                text = decode_content(child)
                if text:
                    parts.append(text)
        return " ".join(dict.fromkeys(parts))
    if isinstance(value, list):
        return " ".join(filter(None, (decode_content(item) for item in value)))
    return " ".join(str(value).split())


def extract_chat_candidates(payload: Any) -> list[dict[str, str]]:
    seen: set[str] = set()
    chats: list[dict[str, str]] = []
    for item in iter_dicts(payload):
        chat_id = first_text(item, ("chat_id", "chatId", "open_chat_id"))
        if not chat_id or not chat_id.startswith("oc_") or chat_id in seen:
            continue
        seen.add(chat_id)
        chats.append(
            {
                "chat_id": chat_id,
                "name": first_text(
                    item,
                    (
                        "name",
                        "chat_name",
                        "title",
                        "display_name",
                        "description",
                    ),
                ),
            }
        )
    return chats


def normalize_message(record: dict[str, Any], *, source: str) -> dict[str, Any]:
    content = decode_content(record.get("content") or record.get("body") or record.get("text"))
    return {
        "source": str(record.get("source") or source),
        "message_id": first_text(record, ("message_id", "messageId", "id")),
        "chat_id": first_text(record, ("chat_id", "chatId", "open_chat_id")),
        "chat_name": first_text(record, ("chat_name", "chatName", "chat_title", "name")),
        "sender": first_text(record, ("sender_name", "senderName", "sender", "user_name")),
        "message_type": first_text(record, ("message_type", "msg_type", "type")),
        "create_time": first_text(record, ("create_time", "created_at", "timestamp")),
        "content": content,
    }


def extract_messages(payload: Any, *, source: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    messages: list[dict[str, Any]] = []
    for item in iter_dicts(payload):
        if not isinstance(item, dict):
            continue
        message = normalize_message(item, source=source)
        message_id = str(message.get("message_id") or "")
        if not message_id or not message_id.startswith(("om_", "omt_")) or message_id in seen:
            continue
        seen.add(message_id)
        messages.append(message)
    return messages


def looks_actionable(text: str) -> bool:
    lowered = text.lower()
    patterns = (
        "?",
        "？",
        "吗",
        "么",
        "能否",
        "可以",
        "帮",
        "麻烦",
        "看下",
        "确认",
        "需要",
        "同步",
        "安排",
        "please",
        "review",
        "check",
        "todo",
        "follow",
        "confirm",
        "fyi",
    )
    return any(pattern in lowered for pattern in patterns)


def looks_weekly_material(text: str) -> bool:
    lowered = text.lower()
    patterns = (
        "完成",
        "推进",
        "上线",
        "发布",
        "修复",
        "评审",
        "讨论",
        "会议",
        "方案",
        "需求",
        "问题",
        "风险",
        "素材",
        "周报",
        "blocker",
        "todo",
        "review",
        "launch",
        "release",
        "signal",
        "metrics",
    )
    return any(pattern in lowered for pattern in patterns)


def draft_reply(message: dict[str, Any], style: str) -> str:
    content = str(message.get("content") or "")
    lowered = content.lower()
    if "review" in lowered or "评审" in content or "看下" in content:
        base = "收到，我先看一下，有结论后同步。"
    elif "确认" in content or "confirm" in lowered or "吗" in content or "？" in content or "?" in content:
        base = "收到，我确认一下现状，稍后给你反馈。"
    elif "安排" in content or "同步" in content:
        base = "收到，我会整理一下进展和下一步。"
    else:
        base = "收到，我看一下这件事，稍后同步。"
    if "正式" in style:
        return base.replace("收到，", "收到，感谢提醒。")
    if "友好" in style:
        return base + " 辛苦。"
    return base


def render_message_line(message: dict[str, Any]) -> str:
    chat = message.get("chat_name") or message.get("chat_id") or "unknown-chat"
    sender = message.get("sender") or "unknown-sender"
    content = str(message.get("content") or "").strip()
    if len(content) > 240:
        content = content[:237].rstrip() + "..."
    return f"- [{message.get('source')}] {chat} / {sender} / {message.get('message_id')}: {content}"


def shell_command(argv: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


def build_review_items(
    actionable: list[dict[str, Any]],
    *,
    style: str,
    cli_bin: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, message in enumerate(actionable, start=1):
        message_id = str(message.get("message_id") or "")
        reply_text = draft_reply(message, style)
        review_id = f"reply_{index:03d}_{slug(message_id)}"
        dry_run_argv = [
            cli_bin,
            "im",
            "+messages-reply",
            "--as",
            "user",
            "--message-id",
            message_id,
            "--text",
            reply_text,
            "--reply-in-thread",
            "--dry-run",
        ]
        excerpt = str(message.get("content") or "").strip()
        if len(excerpt) > 500:
            excerpt = excerpt[:497].rstrip() + "..."
        items.append(
            {
                "schema_version": "lark_digital_clone_reply_review_item_v0",
                "review_id": review_id,
                "status": "needs_user_approval",
                "decision": "needs_user_approval",
                "chat_id": message.get("chat_id") or "",
                "chat_label": message.get("chat_name") or message.get("chat_id") or "unknown-chat",
                "message_id": message_id,
                "sender": message.get("sender") or "",
                "source": message.get("source") or "",
                "source_excerpt": excerpt,
                "reply_text": reply_text,
                "dry_run_argv": dry_run_argv,
                "dry_run_command": shell_command(dry_run_argv),
            }
        )
    return items


def build_loopx_todo_packet(
    *,
    review_items: list[dict[str, Any]],
    weekly: list[dict[str, Any]],
) -> dict[str, Any]:
    user_todos: list[dict[str, Any]] = []
    agent_todos: list[dict[str, Any]] = []
    for item in review_items:
        user_todos.append(
            {
                "schema_version": "loopx_local_todo_candidate_v0",
                "task_class": "user_gate",
                "priority": "P0",
                "title": f"Approve or edit Lark reply draft for {item['chat_label']}",
                "source_id": item["review_id"],
                "gate": {
                    "question": "是否发送这条 Lark 回复？如需发送，请确认或修改 reply_text。",
                    "message_id": item["message_id"],
                    "reply_text": item["reply_text"],
                    "dry_run_command": item["dry_run_command"],
                },
            }
        )
    if weekly:
        agent_todos.append(
            {
                "schema_version": "loopx_local_todo_candidate_v0",
                "task_class": "advancement_task",
                "priority": "P1",
                "title": "Turn Lark weekly material candidates into a concise weekly report section",
                "source_id": "weekly_material.md",
                "evidence_count": len(weekly),
                "next_action": "Group by project, classify ownership, and keep links/message ids as evidence pointers.",
            }
        )
    return {
        "schema_version": LARK_DIGITAL_CLONE_TODO_PACKET_SCHEMA_VERSION,
        "source": "loopx_lark_digital_clone_scan",
        "user_todos": user_todos,
        "agent_todos": agent_todos,
        "write_boundary": "candidate_packet_only",
    }


def build_outputs(
    messages: list[dict[str, Any]],
    *,
    style: str,
    cli_bin: str,
) -> dict[str, str]:
    actionable = [item for item in messages if looks_actionable(str(item.get("content") or ""))]
    weekly = [item for item in messages if looks_weekly_material(str(item.get("content") or ""))]

    todo_lines = [
        "# 今日待回复",
        "",
        f"- 候选消息数：{len(actionable)}",
        "- 发送边界：仅草稿；真实发送前逐条确认。",
        "",
    ]
    todo_lines.extend(render_message_line(item) for item in actionable)

    draft_lines = [
        "# 回复草稿",
        "",
        f"- 风格：{style}",
        "- 发送边界：仅草稿；真实发送前逐条确认。",
        "",
    ]
    for index, item in enumerate(actionable, start=1):
        draft_lines.extend(
            [
                f"## {index}. {item.get('chat_name') or item.get('chat_id') or 'unknown-chat'}",
                "",
                f"- message_id: `{item.get('message_id')}`",
                f"- sender: {item.get('sender') or 'unknown'}",
                f"- 原文摘要: {str(item.get('content') or '')[:500]}",
                "",
                "建议回复：",
                "",
                draft_reply(item, style),
                "",
            ]
        )

    weekly_lines = [
        "# 周报素材",
        "",
        f"- 候选素材数：{len(weekly)}",
        "- 来源：Lark 消息只读扫描。",
        "",
        "## 可归档线索",
        "",
    ]
    weekly_lines.extend(render_message_line(item) for item in weekly)

    review_items = build_review_items(actionable, style=style, cli_bin=cli_bin)
    send_lines = [
        "# 发送确认队列",
        "",
        "- 状态：仅预览；所有发送命令都带 `--dry-run`。",
        "- 真实发送前必须逐条确认目标消息和回复文本。",
        "",
    ]
    for index, item in enumerate(review_items, start=1):
        send_lines.extend(
            [
                f"## {index}. {item['chat_label']}",
                "",
                f"- review_id: `{item['review_id']}`",
                f"- message_id: `{item['message_id']}`",
                f"- decision: `{item['decision']}`",
                f"- 原文摘要: {item['source_excerpt']}",
                "",
                "回复草稿：",
                "",
                item["reply_text"],
                "",
                "发送预览命令：",
                "",
                "```bash",
                item["dry_run_command"],
                "```",
                "",
            ]
        )

    loopx_packet = build_loopx_todo_packet(
        review_items=review_items,
        weekly=weekly,
    )

    return {
        "today_todo.md": "\n".join(todo_lines).rstrip() + "\n",
        "reply_drafts.md": "\n".join(draft_lines).rstrip() + "\n",
        "weekly_material.md": "\n".join(weekly_lines).rstrip() + "\n",
        "send_review.md": "\n".join(send_lines).rstrip() + "\n",
        "review_queue.json": json.dumps(
            {
                "schema_version": "lark_digital_clone_review_queue_v0",
                "send_boundary": "preview_only_no_send",
                "items": review_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        "loopx_todo_packet.json": json.dumps(loopx_packet, ensure_ascii=False, indent=2) + "\n",
    }


def command_payload(result: CommandResult) -> dict[str, Any]:
    return {
        "argv": result.argv,
        "returncode": result.returncode,
        "stdout_json": parse_json(result.stdout),
        "stderr": result.stderr.strip(),
    }


def compact_stdout_summary(stdout_json: Any) -> dict[str, Any]:
    if not isinstance(stdout_json, dict):
        return {"type": type(stdout_json).__name__}
    data = stdout_json.get("data")
    summary: dict[str, Any] = {
        "ok": stdout_json.get("ok"),
    }
    if isinstance(data, dict):
        messages = data.get("messages")
        if isinstance(messages, list):
            summary["message_count"] = len(messages)
        if "total" in data:
            summary["total"] = data.get("total")
        if "has_more" in data:
            summary["has_more"] = data.get("has_more")
        if "page_token" in data:
            summary["has_page_token"] = bool(data.get("page_token"))
    api = stdout_json.get("api")
    if isinstance(api, list):
        summary["dry_run_api_count"] = len(api)
    notice = stdout_json.get("_notice")
    if isinstance(notice, dict) and isinstance(notice.get("update"), dict):
        update = notice["update"]
        summary["update_notice"] = {
            "current": update.get("current"),
            "latest": update.get("latest"),
            "message": update.get("message"),
        }
    if stdout_json.get("_parse_error"):
        summary["parse_error"] = True
    return {key: value for key, value in summary.items() if value is not None}


def compact_command_payload(payload: dict[str, Any]) -> dict[str, Any]:
    stderr = str(payload.get("stderr") or "")
    if len(stderr) > 500:
        stderr = stderr[:497].rstrip() + "..."
    return {
        "argv": payload.get("argv") or [],
        "returncode": payload.get("returncode"),
        "stderr": stderr,
        "stdout_summary": compact_stdout_summary(payload.get("stdout_json")),
    }


def load_fixture_messages(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        messages: list[dict[str, Any]] = []
        for item in payload["messages"]:
            if isinstance(item, dict):
                message = normalize_message(item, source=f"fixture:{path.name}")
                if message.get("message_id"):
                    messages.append(message)
        return messages
    return extract_messages(payload, source=f"fixture:{path.name}")


def unique_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_messages: set[str] = set()
    unique: list[dict[str, Any]] = []
    for message in messages:
        message_id = str(message.get("message_id") or "")
        if not message_id or message_id in seen_messages:
            continue
        seen_messages.add(message_id)
        unique.append(message)
    return unique


def run_lark_command(
    argv: list[str],
    *,
    raw_path: Path,
    commands: list[dict[str, Any]],
    runner: CommandRunner,
) -> dict[str, Any]:
    result = runner(argv)
    payload = command_payload(result)
    write_json(raw_path, payload)
    commands.append(compact_command_payload(payload))
    return payload


def run_lark_digital_clone_scan(
    *,
    at_me: bool,
    since: str = "24h",
    out_dir: Path | str = DEFAULT_OUT_DIR,
    chat_keywords: list[str] | None = None,
    chat_ids: list[str] | None = None,
    page_limit: int = 2,
    page_size: int = 20,
    style: str = DEFAULT_STYLE,
    fixture_json: list[str] | None = None,
    execute_read: bool = False,
    skip_auth_check: bool = False,
    cli_bin: str = DEFAULT_CLI_BIN,
    runner: CommandRunner = default_command_runner,
) -> dict[str, Any]:
    keywords = list(chat_keywords or [])
    provided_chat_ids = list(chat_ids or [])
    fixtures = list(fixture_json or [])
    if not at_me and not keywords and not provided_chat_ids and not fixtures:
        raise ValueError("scan requires --at-me, --chat-keyword, --chat-id, or --fixture-json")

    hours = parse_since_to_hours(since)
    out_path = Path(out_dir).expanduser()
    raw_dir = out_path / "raw"
    out_path.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    end = datetime.now().astimezone()
    start = end - timedelta(hours=hours)
    start_text = local_iso(start)
    end_text = local_iso(end)

    fixture_mode = bool(fixtures) and not execute_read
    commands: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    resolved_chats: list[dict[str, str]] = []

    for fixture in fixtures:
        fixture_path = Path(fixture).expanduser()
        fixture_messages = load_fixture_messages(fixture_path)
        messages.extend(fixture_messages)
        write_json(
            raw_dir / f"fixture_{slug(fixture_path.stem)}.json",
            {
                "source_path": str(fixture_path),
                "message_count": len(fixture_messages),
                "messages": fixture_messages,
            },
        )

    if not fixture_mode and not skip_auth_check:
        auth_result = runner([cli_bin, "auth", "status"])
        auth_payload = command_payload(auth_result)
        write_json(raw_dir / "auth_status.json", auth_payload)
        commands.append(compact_command_payload(auth_payload))

    if not fixture_mode and at_me:
        argv = [
            cli_bin,
            "im",
            "+messages-search",
            "--as",
            "user",
            "--is-at-me",
            "--start",
            start_text,
            "--end",
            end_text,
            "--page-size",
            str(page_size),
            "--page-limit",
            str(page_limit),
            "--page-all",
            "--format",
            "json",
        ]
        if not execute_read:
            argv.append("--dry-run")
        payload = run_lark_command(
            argv,
            raw_path=raw_dir / "at_me_messages.json",
            commands=commands,
            runner=runner,
        )
        if execute_read and payload.get("returncode") == 0:
            messages.extend(extract_messages(payload.get("stdout_json"), source="at_me"))

    scan_chat_ids = list(dict.fromkeys(provided_chat_ids))
    if not fixture_mode:
        for keyword in keywords:
            argv = [
                cli_bin,
                "im",
                "+chat-search",
                "--as",
                "user",
                "--query",
                keyword,
                "--format",
                "json",
            ]
            if not execute_read:
                argv.append("--dry-run")
            payload = run_lark_command(
                argv,
                raw_path=raw_dir / f"chat_search_{slug(keyword)}.json",
                commands=commands,
                runner=runner,
            )
            if execute_read and payload.get("returncode") == 0:
                chats = extract_chat_candidates(payload.get("stdout_json"))
                resolved_chats.extend(chats)
                scan_chat_ids.extend(chat["chat_id"] for chat in chats)

        scan_chat_ids = list(dict.fromkeys(scan_chat_ids))
        for chat_id in scan_chat_ids:
            argv = [
                cli_bin,
                "im",
                "+messages-search",
                "--as",
                "user",
                "--chat-id",
                chat_id,
                "--start",
                start_text,
                "--end",
                end_text,
                "--page-size",
                str(page_size),
                "--page-limit",
                str(page_limit),
                "--page-all",
                "--format",
                "json",
            ]
            if not execute_read:
                argv.append("--dry-run")
            payload = run_lark_command(
                argv,
                raw_path=raw_dir / f"chat_messages_{slug(chat_id)}.json",
                commands=commands,
                runner=runner,
            )
            if execute_read and payload.get("returncode") == 0:
                messages.extend(extract_messages(payload.get("stdout_json"), source=f"chat:{chat_id}"))

    deduped_messages = unique_messages(messages)
    outputs = build_outputs(deduped_messages, style=style, cli_bin=cli_bin)
    for name, text in outputs.items():
        write_text(out_path / name, text)

    artifacts = {
        "summary_json": str(out_path / "summary.json"),
        "today_todo": str(out_path / "today_todo.md"),
        "reply_drafts": str(out_path / "reply_drafts.md"),
        "weekly_material": str(out_path / "weekly_material.md"),
        "send_review": str(out_path / "send_review.md"),
        "review_queue": str(out_path / "review_queue.json"),
        "loopx_todo_packet": str(out_path / "loopx_todo_packet.json"),
        "raw_dir": str(raw_dir),
    }
    summary = {
        "message_count": len(deduped_messages),
        "actionable_count": sum(looks_actionable(str(item.get("content") or "")) for item in deduped_messages),
        "weekly_material_count": sum(
            looks_weekly_material(str(item.get("content") or "")) for item in deduped_messages
        ),
    }
    ok = all(item.get("returncode") == 0 for item in commands)
    payload = {
        "ok": ok,
        "schema_version": LARK_DIGITAL_CLONE_SCAN_SCHEMA_VERSION,
        "mode": "fixture" if fixture_mode else ("execute_read" if execute_read else "dry_run"),
        "time_range": {"start": start_text, "end": end_text, "since": since, "hours": hours},
        "scan": {
            "at_me": at_me,
            "chat_keywords": keywords,
            "provided_chat_ids": provided_chat_ids,
            "resolved_chats": resolved_chats,
            "page_limit": page_limit,
            "page_size": page_size,
        },
        "summary": summary,
        "artifacts": artifacts,
        "read_boundary": {
            "external_reads_performed": bool(execute_read),
            "fixture_paths": fixtures,
            "raw_lark_payloads_stay_under": str(raw_dir),
        },
        "write_boundary": {
            "external_writes_performed": False,
            "loopx_registry_writes_performed": False,
            "send_requires_user_approval": True,
            "todo_packet_role": "candidate_only",
        },
        "commands": commands,
    }
    write_json(out_path / "summary.json", payload)
    return payload


def render_lark_digital_clone_scan_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    read_boundary = payload.get("read_boundary") if isinstance(payload.get("read_boundary"), dict) else {}
    write_boundary = payload.get("write_boundary") if isinstance(payload.get("write_boundary"), dict) else {}
    lines = [
        "# LoopX Lark Digital Clone Scan",
        "",
        f"- ok: `{bool(payload.get('ok'))}`",
        f"- mode: `{payload.get('mode')}`",
        f"- messages: `{summary.get('message_count', 0)}`",
        f"- actionable: `{summary.get('actionable_count', 0)}`",
        f"- weekly_material: `{summary.get('weekly_material_count', 0)}`",
        f"- external_reads_performed: `{read_boundary.get('external_reads_performed')}`",
        f"- external_writes_performed: `{write_boundary.get('external_writes_performed')}`",
        "",
        "## Artifacts",
        "",
    ]
    for key in (
        "today_todo",
        "reply_drafts",
        "weekly_material",
        "send_review",
        "review_queue",
        "loopx_todo_packet",
        "summary_json",
    ):
        value = artifacts.get(key)
        if value:
            lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Next",
            "",
            "- Review `reply_drafts.md` and `send_review.md` before any Lark send.",
            "- Import `loopx_todo_packet.json` only after choosing a LoopX write path.",
            "",
        ]
    )
    return "\n".join(lines)
