from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.cli import build_parser, main, output_format, resolve_global_output_format
from loopx.cli_commands import todo as todo_command
from loopx.cli_commands.quota_request import validate_quota_command_request
from loopx.cli_commands.todo_argument_validation import (
    validate_todo_add_options,
    validate_todo_archive_completed_options,
    validate_todo_capture_followups_options,
    validate_todo_claim_options,
    validate_todo_complete_options,
    validate_todo_list_options,
    validate_todo_suggest_options,
    validate_todo_supersede_options,
    validate_todo_update_options,
)


def test_todo_handler_expands_shared_paths_and_keeps_suggest_project_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    captured_list: dict[str, object] = {}
    captured_suggest: dict[str, object] = {}

    def fake_list_goal_todos(**kwargs: object) -> dict[str, object]:
        captured_list.update(kwargs)
        return {"ok": True, "dry_run": True}

    def fake_suggestion_packet(**kwargs: object) -> dict[str, object]:
        captured_suggest.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(todo_command, "list_goal_todos", fake_list_goal_todos)
    monkeypatch.setattr(
        todo_command,
        "build_todo_suggestion_prompt_packet",
        fake_suggestion_packet,
    )
    common = {
        "registry_path": tmp_path / "registry.json",
        "runtime_root_arg": None,
        "print_payload": lambda *_args: None,
        "append_cli_rollout_event": lambda *_args, **_kwargs: {},
    }

    list_args = build_parser().parse_args(
        [
            "todo",
            "list",
            "--goal-id",
            "example-goal",
            "--project",
            "~/project",
            "--state-file",
            "~/ACTIVE_GOAL_STATE.md",
        ]
    )
    assert todo_command.handle_todo_command(list_args, **common) == 0
    assert captured_list["project"] == tmp_path / "project"
    assert captured_list["state_file"] == tmp_path / "ACTIVE_GOAL_STATE.md"

    suggest_args = build_parser().parse_args(
        [
            "todo",
            "suggest",
            "--goal-id",
            "example-goal",
            "--project",
            "~/project",
        ]
    )
    assert todo_command.handle_todo_command(suggest_args, **common) == 0
    assert captured_suggest["project"] == tmp_path / "project"
    assert "state_file" not in captured_suggest


def test_todo_requires_explicit_command_without_mutating_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_add_is_called(**_kwargs: object) -> dict[str, object]:
        pytest.fail("omitting the todo command must not fall back to todo add")

    monkeypatch.setattr(todo_command, "add_goal_todo", fail_if_add_is_called)

    exit_code = main(
        [
            "--format",
            "json",
            "todo",
            "--goal-id",
            "example-goal",
            "--todo-id",
            "todo_example",
            "--role",
            "agent",
            "--text",
            "Accidental replacement todo.",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["added"] is False
    assert payload["error"] == (
        "`loopx todo` requires an explicit command; use `loopx todo add`, "
        "`loopx todo claim`, `loopx todo update`, or another command shown "
        "by `loopx todo --help`"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["status", "--goal-id", "example-goal", "--project", "."],
        ["quota", "should-run", "--goal-id", "example-goal", "--project", "."],
    ],
)
def test_unsupported_project_option_is_not_misparsed_as_projection_cache_ttl(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "unrecognized arguments: --project ." in stderr
    assert "projection-cache-ttl-seconds" not in stderr
    assert "invalid int value" not in stderr


def test_quota_include_detail_rejects_unknown_section(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "quota",
                "should-run",
                "--goal-id",
                "example-goal",
                "--include-detail",
                "unknown",
            ]
        )

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "invalid choice: 'unknown'" in stderr
    assert "--include-detail" in stderr


def test_quota_include_detail_rejects_non_should_run_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--format",
            "json",
            "quota",
            "status",
            "--include-detail",
            "scheduler",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == (
        "--include-detail is only valid with `quota should-run` or "
        "`quota monitor-poll`"
    )


@pytest.mark.parametrize(
    ("command", "section"),
    [
        ("should-run", "decisions"),
        ("monitor-poll", "scheduler"),
    ],
)
def test_quota_include_detail_rejects_other_command_sections(
    command: str,
    section: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--format",
            "json",
            "quota",
            command,
            "--goal-id",
            "example-goal",
            "--include-detail",
            section,
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["reason"] == (
        f"`quota {command}` does not accept --include-detail {section}"
    )


def test_todo_list_validation_preserves_exact_unsupported_diagnostic() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "list",
            "--goal-id",
            "example-goal",
            "--note",
            "not accepted",
            "--evidence",
            "not accepted",
        ]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_list_options(args)

    assert str(exc_info.value) == (
        "todo list only accepts --goal-id, optional --role, --status, --todo-id, "
        "--agent-id, --project, --state-file, --dry-run, and --format; unsupported: "
        "--note, --evidence"
    )


def test_todo_list_validation_accepts_read_filters() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "list",
            "--goal-id",
            "example-goal",
            "--role",
            "agent",
            "--status",
            "open",
            "--todo-id",
            "todo_example",
            "--agent-id",
            "codex-example",
            "--project",
            ".",
            "--state-file",
            "ACTIVE_GOAL_STATE.md",
            "--dry-run",
        ]
    )

    validate_todo_list_options(args)


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        ([], "todo add requires --role"),
        (["--role", "agent"], "todo add requires --text"),
        (
            [
                "--role",
                "agent",
                "--text",
                "Continue.",
                "--decision-outcome",
                "approve",
                "--follow-up",
                "Later.",
            ],
            "todo add does not accept --decision-outcome; record it on completion",
        ),
        (
            [
                "--role",
                "agent",
                "--text",
                "Continue.",
                "--clear-explore-result-node-refs",
            ],
            "todo add accepts --explore-result-node-ref but not "
            "--clear-explore-result-node-refs",
        ),
        (
            [
                "--role",
                "agent",
                "--text",
                "Continue.",
                "--next-required-capability",
                "network",
            ],
            "todo add does not support --next-required-capability",
        ),
        (
            [
                "--role",
                "agent",
                "--text",
                "Continue.",
                "--successor-todo-id",
                "todo_successor",
            ],
            "todo add does not support --successor-todo-id; use todo update/complete "
            "to link existing successor work",
        ),
    ],
)
def test_todo_add_validation_preserves_exact_diagnostics(
    extra_args: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(
        ["todo", "add", "--goal-id", "example-goal", *extra_args]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_add_options(args)

    assert str(exc_info.value) == expected


def test_todo_add_validation_accepts_add_fields() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "add",
            "--goal-id",
            "example-goal",
            "--role",
            "agent",
            "--text",
            "Continue.",
            "--claimed-by",
            "codex-example",
            "--required-capability",
            "shell",
            "--explore-result-node-ref",
            "result_1",
        ]
    )

    validate_todo_add_options(args)


def test_deprecated_scheduler_detail_alias_is_hidden_from_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["quota", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--include-detail" in help_text
    assert "--include-scheduler-detail" not in help_text


@pytest.mark.parametrize(
    (
        "command",
        "goal_id",
        "agent_id",
        "void_generated_at",
        "dry_run",
        "execute",
        "expected",
    ),
    [
        (
            "should-run",
            None,
            None,
            None,
            False,
            False,
            "`loopx quota should-run` requires --goal-id",
        ),
        (
            "scheduler-ack-current",
            "goal",
            None,
            None,
            False,
            False,
            "`loopx quota scheduler-ack-current` requires --agent-id",
        ),
        (
            "spend-slot",
            "goal",
            None,
            None,
            True,
            True,
            "`loopx quota spend-slot` accepts only one of --dry-run or --execute",
        ),
        (
            "void-slot",
            "goal",
            None,
            None,
            True,
            True,
            "`loopx quota void-slot` requires --void-generated-at",
        ),
    ],
)
def test_quota_command_request_validation_preserves_exact_diagnostics(
    command: str,
    goal_id: str | None,
    agent_id: str | None,
    void_generated_at: str | None,
    dry_run: bool,
    execute: bool,
    expected: str,
) -> None:
    args = build_parser().parse_args(["quota", command])
    args.goal_id = goal_id
    args.agent_id = agent_id
    args.void_generated_at = void_generated_at
    args.dry_run = dry_run
    args.execute = execute

    with pytest.raises(ValueError) as exc_info:
        validate_quota_command_request(args)

    assert str(exc_info.value) == expected


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        ([], "todo claim requires --todo-id"),
        (
            ["--todo-id", "todo_example"],
            "todo claim requires --claimed-by",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--claimed-by",
                "codex-example",
                "--clear-claim",
            ],
            "todo claim requires --claimed-by and does not support --clear-claim",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--claimed-by",
                "codex-example",
                "--decision-outcome",
                "approve",
                "--next-agent-todo",
                "Continue the work.",
            ],
            "todo claim only accepts --todo-id, --claimed-by, --agent-id, optional --role, "
            "--project, --state-file, and --dry-run; unsupported: "
            "--decision-outcome, --next-agent-todo",
        ),
    ],
)
def test_todo_claim_validation_preserves_exact_diagnostics(
    extra_args: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(
        ["todo", "claim", "--goal-id", "example-goal", *extra_args]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_claim_options(args)

    assert str(exc_info.value) == expected


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        ([], "todo update requires --todo-id"),
        (
            [
                "--todo-id",
                "todo_example",
                "--claimed-by",
                "codex-example",
                "--clear-claim",
            ],
            "todo update accepts either --claimed-by or --clear-claim, not both",
        ),
        (
            ["--todo-id", "todo_example"],
            "todo update requires at least one mutable todo field",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--no-follow-up",
            ],
            "--no-follow-up requires --note, --reason, or --evidence",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--note",
                "validated",
                "--decision-outcome",
                "approve",
            ],
            "todo update does not accept --decision-outcome; use todo complete",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--next-required-capability",
                "network",
            ],
            "todo update requires at least one mutable todo field",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--note",
                "validated",
                "--next-required-capability",
                "network",
            ],
            "todo update does not support --next-required-capability",
        ),
    ],
)
def test_todo_update_validation_preserves_exact_diagnostics(
    extra_args: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(
        ["todo", "update", "--goal-id", "example-goal", *extra_args]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_update_options(args)

    assert str(exc_info.value) == expected


def test_todo_update_validation_accepts_a_mutable_field() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "update",
            "--goal-id",
            "example-goal",
            "--todo-id",
            "todo_example",
            "--note",
            "validated",
        ]
    )

    validate_todo_update_options(args)


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        ([], "todo complete requires --todo-id"),
        (
            ["--todo-id", "todo_example", "--explore-result-node-ref", "result_1"],
            "todo complete does not update --explore-result-node-ref; "
            "use todo update first",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--claimed-by",
                "codex-example",
                "--clear-claim",
            ],
            "todo complete accepts either --claimed-by or --clear-claim, not both",
        ),
        (
            ["--todo-id", "todo_example", "--task-repository", "git:example/repo"],
            "todo complete does not update current todo routing metadata; "
            "use todo update first",
        ),
        (
            ["--todo-id", "todo_example", "--cadence", "1h"],
            "todo complete does not update target or monitor schedule metadata; "
            "use todo update before completion",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--no-follow-up",
                "--next-agent-todo",
                "Continue.",
            ],
            "--no-follow-up cannot be combined with successor todos",
        ),
        (
            [
                "--todo-id",
                "todo_example",
                "--successor-todo-id",
                "todo_successor",
                "--next-agent-todo",
                "Continue.",
            ],
            "--successor-todo-id links existing work and cannot be combined with "
            "--next-agent-todo or --next-user-todo",
        ),
        (
            ["--todo-id", "todo_example", "--no-follow-up"],
            "--no-follow-up requires --note or --evidence",
        ),
        (
            ["--todo-id", "todo_example", "--continuation-policy", "same_agent_non_delivery"],
            "todo complete does not update --continuation-policy; use todo update first",
        ),
        (
            ["--todo-id", "todo_example", "--task-lease-expected-version", "2"],
            "--task-lease-expected-version requires --task-lease-idempotency-key",
        ),
        (
            ["--todo-id", "todo_example", "--next-user-todo", "Approve."],
            "--next-user-todo requires explicit --next-user-task-class "
            "user_action|user_gate",
        ),
    ],
)
def test_todo_complete_validation_preserves_exact_diagnostics(
    extra_args: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(
        ["todo", "complete", "--goal-id", "example-goal", *extra_args]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_complete_options(args)

    assert str(exc_info.value) == expected


def test_todo_complete_preserves_typed_task_lease_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def reject_stale_instance(**_kwargs: object) -> dict[str, object]:
        raise todo_command.TaskLeaseError(
            "todo has an active task lease",
            code="lease_fence_required",
            payload={"lease_version": 3},
        )

    captured: dict[str, object] = {}
    monkeypatch.setattr(todo_command, "complete_goal_todo", reject_stale_instance)
    args = build_parser().parse_args(
        [
            "todo",
            "complete",
            "--goal-id",
            "example-goal",
            "--todo-id",
            "todo_example",
            "--claimed-by",
            "codex-example",
        ]
    )

    exit_code = todo_command.handle_todo_command(
        args,
        registry_path=tmp_path / "registry.json",
        runtime_root_arg=None,
        print_payload=lambda payload, *_args: captured.update(payload),
        append_cli_rollout_event=lambda *_args, **_kwargs: {},
        format_name="json",
    )

    assert exit_code == 1
    assert captured["error_code"] == "lease_fence_required"
    assert captured["lease_version"] == 3


def test_todo_complete_validation_accepts_no_follow_up_with_evidence() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "complete",
            "--goal-id",
            "example-goal",
            "--todo-id",
            "todo_example",
            "--no-follow-up",
            "--evidence",
            "validated",
        ]
    )

    validate_todo_complete_options(args)


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        ([], "todo supersede requires --todo-id"),
        (
            ["--todo-id", "todo_example", "--explore-result-node-ref", "result_1"],
            "todo supersede does not update --explore-result-node-ref; "
            "use todo update first",
        ),
        (
            ["--todo-id", "todo_example", "--decision-outcome", "approve"],
            "todo supersede does not accept --decision-outcome; use todo complete",
        ),
        (
            ["--todo-id", "todo_example", "--claimed-by", "codex-example"],
            "todo supersede does not support --claimed-by; use --next-claimed-by "
            "to assign the successor, or omit it to inherit the superseded todo "
            "owner when present",
        ),
        (
            ["--todo-id", "todo_example", "--self-merged"],
            "todo supersede does not support --self-merged",
        ),
        (
            ["--todo-id", "todo_example", "--no-follow-up"],
            "todo supersede does not support --no-follow-up",
        ),
        (
            ["--todo-id", "todo_example", "--continuation-policy", "same_agent_non_delivery"],
            "todo supersede does not update --continuation-policy; use todo update first",
        ),
        (
            ["--todo-id", "todo_example", "--next-user-todo", "Approve."],
            "--next-user-todo requires explicit --next-user-task-class "
            "user_action|user_gate",
        ),
        (
            ["--todo-id", "todo_example", "--blocks-agent", "codex-example"],
            "todo supersede does not update current todo routing metadata; "
            "use todo update first",
        ),
        (
            ["--todo-id", "todo_example", "--successor-todo-id", "todo_successor"],
            "todo supersede does not support --successor-todo-id; "
            "use --next-agent-todo or update the source todo before supersede",
        ),
        (
            ["--todo-id", "todo_example", "--target-key", "monitor"],
            "todo supersede does not update target or monitor schedule metadata; "
            "use todo update before supersede",
        ),
    ],
)
def test_todo_supersede_validation_preserves_exact_diagnostics(
    extra_args: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(
        ["todo", "supersede", "--goal-id", "example-goal", *extra_args]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_supersede_options(args)

    assert str(exc_info.value) == expected


def test_todo_supersede_validation_accepts_successor_creation() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "supersede",
            "--goal-id",
            "example-goal",
            "--todo-id",
            "todo_example",
            "--next-agent-todo",
            "Continue.",
        ]
    )

    validate_todo_supersede_options(args)


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        (
            ["--decision-outcome", "approve"],
            "todo archive-completed does not support --decision-outcome",
        ),
        (
            ["--claimed-by", "codex-example"],
            "todo archive-completed does not support --claimed-by or --clear-claim",
        ),
        (
            ["--excluded-agent", "codex-example"],
            "todo archive-completed does not support executor exclusions",
        ),
        (
            ["--next-claimed-by", "codex-example"],
            "todo archive-completed does not support --next-claimed-by",
        ),
        (
            ["--next-task-repository", "git:github.com/example/repo"],
            "todo archive-completed does not support successor routing metadata",
        ),
        (
            ["--self-merged"],
            "todo archive-completed does not support --self-merged",
        ),
        (
            ["--no-follow-up"],
            "todo archive-completed does not support --no-follow-up",
        ),
        (
            ["--follow-up", "Continue."],
            "todo archive-completed does not support --follow-up; "
            "use `todo capture-followups`",
        ),
        (
            ["--successor-todo-id", "todo_successor"],
            "todo archive-completed does not support --successor-todo-id",
        ),
    ],
)
def test_todo_archive_completed_validation_preserves_exact_diagnostics(
    extra_args: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(
        ["todo", "archive-completed", "--goal-id", "example-goal", *extra_args]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_archive_completed_options(args)

    assert str(exc_info.value) == expected


def test_todo_archive_completed_validation_accepts_role_and_limit() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "archive-completed",
            "--goal-id",
            "example-goal",
            "--role",
            "user",
            "--max-active-done",
            "7",
        ]
    )

    validate_todo_archive_completed_options(args)


def test_todo_suggest_validation_preserves_exact_unsupported_diagnostic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--format",
            "json",
            "todo",
            "suggest",
            "--goal-id",
            "example-goal",
            "--todo-id",
            "todo_example",
            "--note",
            "not accepted",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == (
        "todo suggest only accepts --goal-id, optional --project, --agent-id, "
        "--from, --limit, --trigger, --dry-run, and --format; unsupported: "
        "--todo-id, --note"
    )


def test_todo_suggest_validation_accepts_suggestion_scope_options() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "suggest",
            "--goal-id",
            "example-goal",
            "--agent-id",
            "codex-example",
            "--from",
            "recent-repo",
            "--limit",
            "3",
            "--trigger",
            "quality-watch",
        ]
    )

    validate_todo_suggest_options(args)


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [
        (
            ["--role", "agent"],
            "todo capture-followups always records agent todos; do not pass --role",
        ),
        (
            ["--claimed-by", "codex-example"],
            "todo capture-followups writes unclaimed todos; do not pass --claimed-by",
        ),
        (
            ["--todo-id", "todo_example", "--note", "not accepted"],
            "todo capture-followups only accepts --goal-id, --follow-up, optional "
            "--text shorthand, --evidence, routing metadata, --project, --state-file, "
            "and --dry-run; unsupported: --todo-id, --note",
        ),
    ],
)
def test_todo_capture_followups_validation_preserves_exact_diagnostics(
    extra_args: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(
        ["todo", "capture-followups", "--goal-id", "example-goal", *extra_args]
    )

    with pytest.raises(ValueError) as exc_info:
        validate_todo_capture_followups_options(args)

    assert str(exc_info.value) == expected


def test_todo_capture_followups_validation_accepts_routing_options() -> None:
    args = build_parser().parse_args(
        [
            "todo",
            "capture-followups",
            "--goal-id",
            "example-goal",
            "--follow-up",
            "Continue.",
            "--text",
            "Then validate.",
            "--evidence",
            "tests/test_cli_argument_diagnostics.py",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "implement",
            "--continuation-policy",
            "same_agent_non_delivery",
            "--required-write-scope",
            "tests/**",
            "--required-capability",
            "shell",
            "--target-capability",
            "quality",
            "--required-decision-scope",
            "merge",
            "--state-file",
            "ACTIVE_GOAL_STATE.md",
        ]
    )

    validate_todo_capture_followups_options(args)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["quota", "should-run"], "json"),
        (["quota", "status"], "markdown"),
        (["status"], "markdown"),
        (["diagnose"], "markdown"),
        (["review-packet", "--goal-id", "example-goal"], "markdown"),
    ],
)
def test_only_quota_should_run_defaults_to_json(
    argv: list[str],
    expected: str,
) -> None:
    args = build_parser().parse_args(argv)

    assert resolve_global_output_format(args) == expected


@pytest.mark.parametrize("explicit_format", ["markdown", "json"])
def test_explicit_global_format_overrides_quota_should_run_default(
    explicit_format: str,
) -> None:
    args = build_parser().parse_args(
        ["--format", explicit_format, "quota", "should-run"]
    )

    assert resolve_global_output_format(args) == explicit_format


def test_subcommand_format_keeps_precedence_over_resolved_global_default() -> None:
    args = build_parser().parse_args(["status", "--format", "json"])
    args.format = resolve_global_output_format(args)

    assert output_format(args) == "json"
