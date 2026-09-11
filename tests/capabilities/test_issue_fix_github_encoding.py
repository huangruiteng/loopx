"""GitHub UTF-8 output must not depend on the Python host's ANSI code page."""

from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from loopx.capabilities.issue_fix import candidate_evidence, metadata_preview
from loopx.cli import main as cli_main


@pytest.fixture
def github_output(monkeypatch):
    # Model Windows cp936 on any CI host, without replacing the real pipe decoder.
    monkeypatch.setattr(subprocess, "_text_encoding", lambda: "gbk")

    def install(module, stdout: bytes, *, stderr: bytes = b"", returncode: int = 0):
        def run(command, **kwargs):
            assert command[1] == "api"
            script = (
                "import sys; "
                f"sys.stdout.buffer.write({stdout!r}); "
                f"sys.stderr.buffer.write({stderr!r}); "
                f"sys.exit({returncode})"
            )
            return subprocess.run([sys.executable, "-c", script], **kwargs)

        # Only substitute the capability's transport, never subprocess.run globally.
        monkeypatch.setattr(
            module,
            "subprocess",
            SimpleNamespace(
                run=run,
                PIPE=subprocess.PIPE,
                TimeoutExpired=subprocess.TimeoutExpired,
            ),
        )
        if module is candidate_evidence:
            monkeypatch.setattr(module, "shutil", SimpleNamespace(which=lambda _: "gh"))

    return install


@pytest.fixture(params=["metadata", "candidate"])
def github_reader(request):
    if request.param == "metadata":
        return (
            metadata_preview,
            lambda: metadata_preview.fetch_github_issue_metadata_payload(
                {"repo": "example/project", "number": 1},
            ),
        )
    return candidate_evidence, lambda: candidate_evidence._run_graphql_pages(
        query="query { fixture }",
        owner="example",
        name="project",
        number=1,
        timeout_seconds=10,
        operation="candidate fixture read",
    )[0]


def test_github_unicode_survives_non_utf8_host(github_output, github_reader):
    module, read = github_reader
    expected = {"title": "修复中文标题 🚀 café", "labels": ["缺陷"]}
    github_output(module, json.dumps(expected, ensure_ascii=False).encode("utf-8"))
    assert read() == expected


def test_github_malformed_byte_does_not_kill_pipe_reader(github_output, github_reader):
    module, read = github_reader
    github_output(module, b'{"title":"before\xffafter"}', stderr=b"warning: \xff")
    assert read() == {"title": "before\ufffdafter"}


def test_github_invalid_json_still_fails(github_output, github_reader):
    module, read = github_reader
    github_output(module, b"not json\xff")
    with pytest.raises(ValueError):
        read()


def test_github_failure_keeps_existing_safe_diagnostic(github_output, github_reader):
    module, read = github_reader
    github_output(module, b"", stderr="内部错误 🚀".encode() + b"\xff", returncode=1)
    with pytest.raises(
        (ValueError, RuntimeError), match="fetch failed|fixture read failed"
    ) as caught:
        read()
    assert "内部错误" not in str(caught.value)
    assert "NoneType" not in str(caught.value)


def test_workflow_plan_fetch_metadata_cli_on_non_utf8_host(
    github_output, tmp_path, capsys
):
    github_output(
        metadata_preview,
        json.dumps(
            {
                "number": 1,
                "state": "open",
                "title": "修复中文标题 🚀",
                "labels": ["bug"],
                "kind": "issue",
                "comments_count": 0,
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    result = cli_main(
        [
            "--registry",
            str(tmp_path / "registry.json"),
            "--format",
            "json",
            "issue-fix",
            "workflow-plan",
            "--url",
            "https://github.com/example/project/issues/1",
            "--fetch-metadata",
            "--no-write-domain-state",
        ]
    )
    captured = capsys.readouterr()
    assert result == 0, captured.out
    assert json.loads(captured.out)["ok"] is True
    assert not (tmp_path / "registry.json").exists()
