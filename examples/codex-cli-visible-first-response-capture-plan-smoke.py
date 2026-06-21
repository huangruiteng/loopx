#!/usr/bin/env python3
"""Smoke-test the Codex CLI visible first-response capture plan."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.codex_cli_probe import (  # noqa: E402
    build_codex_cli_bounded_visible_pilot_adapter,
    build_codex_cli_visible_first_response_capture_plan,
)


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"
DOC = REPO_ROOT / "docs" / "product" / "codex-cli-live-tui-first-message-pilot.md"
PRODUCT_README = REPO_ROOT / "docs" / "product" / "README.md"


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def assert_boundary(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert boundary["capture_plan_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["reads_stdout_stderr"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["writes_loopx_state"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert boundary["manual_paste_primary"] is True, payload
    assert boundary["argv_prompt_rejected"] is True, payload
    assert boundary["success_claim_requires_bounded_adapter"] is True, payload


def assert_capture_plan(payload: dict[str, object]) -> None:
    assert payload["schema_version"] == "codex_cli_visible_first_response_capture_plan_v0"
    assert payload["decision"] == "manual_visible_capture_plan_ready", payload
    assert payload["start_surface"] == "codex_cli_tui_manual_paste", payload
    assert "public-first-response.json" in payload["commands"]["bounded_visible_pilot_adapter"], payload
    assert "public-runtime-idle.json" in payload["commands"]["bounded_visible_pilot_adapter"], payload
    assert "codex-cli-bootstrap-message" in payload["commands"]["bootstrap_message"], payload
    assert "codex-cli-runtime-idle-detector" in payload["commands"]["runtime_idle_detector"], payload
    assert "argv_prompt_used" in payload["sample_first_response_fixture"]["prompt_delivery"], payload
    assert payload["sample_first_response_fixture"]["prompt_delivery"]["argv_prompt_used"] is False
    assert payload["sample_runtime_idle_fixture"]["idle_guard"]["no_running_turn"] is True
    assert "the bootstrap message would have to be passed as argv" in payload["stop_conditions"], payload
    assert_boundary(payload)


def assert_sample_fixtures_pass_adapter(payload: dict[str, object]) -> None:
    passing = build_codex_cli_bounded_visible_pilot_adapter(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        first_response_payload=payload["sample_first_response_fixture"],
        idle_payload=payload["sample_runtime_idle_fixture"],
    )
    assert passing["decision"] == "bounded_visible_pilot_ready_for_success_claim", passing
    assert passing["approved_for_live_tui_success_claim"] is True, passing
    assert passing["blockers"] == [], passing


def assert_cli() -> None:
    cli_json = json.loads(
        run_cli(
            "--format",
            "json",
            "codex-cli-visible-first-response-capture-plan",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
        )
    )
    assert_capture_plan(cli_json)
    assert_sample_fixtures_pass_adapter(cli_json)

    markdown = run_cli(
        "codex-cli-visible-first-response-capture-plan",
        "--project",
        str(PROJECT),
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    assert "# Codex CLI Visible First-Response Capture Plan" in markdown, markdown
    assert "Sample First-Response Fixture" in markdown, markdown
    assert "argv_prompt_rejected" in markdown, markdown
    assert "reads_raw_transcripts" in markdown, markdown

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-first-response-") as tmp:
        tmp_path = Path(tmp)
        first_response = tmp_path / "public-first-response.json"
        idle = tmp_path / "public-runtime-idle.json"
        first_response.write_text(json.dumps(cli_json["sample_first_response_fixture"]))
        idle.write_text(json.dumps(cli_json["sample_runtime_idle_fixture"]))
        adapter = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-bounded-visible-pilot-adapter",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--first-response-fixture",
                str(first_response),
                "--idle-fixture",
                str(idle),
            )
        )
        assert adapter["approved_for_live_tui_success_claim"] is True, adapter


def assert_docs() -> None:
    doc = DOC.read_text(encoding="utf-8")
    readme = PRODUCT_README.read_text(encoding="utf-8")
    assert "codex-cli-visible-first-response-capture-plan" in doc, doc
    assert "public-first-response.json" in doc, doc
    assert "public-runtime-idle.json" in doc, doc
    assert "visible first-response capture plan" in readme, readme
    assert "codex-cli-visible-first-response-capture-plan-smoke.py" in readme, readme


def main() -> int:
    direct = build_codex_cli_visible_first_response_capture_plan(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
    )
    assert_capture_plan(direct)
    assert_sample_fixtures_pass_adapter(direct)
    assert_cli()
    assert_docs()
    print("codex-cli-visible-first-response-capture-plan-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
