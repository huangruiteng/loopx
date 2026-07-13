#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.capabilities.semantic_preference import (  # noqa: E402
    application_receipt,
    provider_doctor,
    recall,
)


def run(*args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def run_failure(*args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result.stderr or result.stdout
    assert "Traceback" not in result.stderr, result.stderr
    return json.loads(result.stdout)


def recall_cli(project: Path, config: Path, surface: str, *, execute: bool = False):
    args = [
        "semantic-preference",
        "recall",
        "--project",
        str(project),
        "--config",
        str(config),
        "--surface",
        surface,
    ]
    return run(*args, *(["--execute"] if execute else []))


with tempfile.TemporaryDirectory(prefix="loopx-semantic-preference-") as raw_temp:
    temp = Path(raw_temp)
    project = temp / "project"
    project.mkdir()
    provider = temp / "provider.py"
    provider.write_text(
        """import json, sys
request = json.load(sys.stdin)
surface = request["surface"]
json.dump({
    "schema_version": "semantic_preference_provider_response_v0",
    "items": [{"preference_ref": f"memory://{surface}", "summary": f"prefer {surface}"}],
}, sys.stdout)
""",
        encoding="utf-8",
    )
    config = temp / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {
                    "id": "fixture_memory",
                    "argv": [sys.executable, str(provider)],
                    "probe_argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "setup_hints": {
                        "install": "Install the fixture provider explicitly.",
                        "configure": "Configure the fixture provider explicitly.",
                    },
                },
                "surfaces": {
                    "issue_fix.pr_description": {"query": "PR description preferences"},
                    "content_ops.draft_language": {
                        "query": "Draft language preferences"
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    for surface in ("issue_fix.pr_description", "content_ops.draft_language"):
        preview = recall_cli(project, config, surface)
        assert preview["status"] == "preview_ready", preview
        recalled = recall_cli(project, config, surface, execute=True)
        assert recalled["status"] == "completed", recalled
        assert recalled["items"][0]["summary"] == f"prefer {surface}", recalled

    doctor_preview = run(
        "semantic-preference",
        "doctor",
        "--project",
        str(project),
        "--config",
        str(config),
    )
    assert doctor_preview["status"] == "probe_required", doctor_preview
    assert doctor_preview["automatic_setup_performed"] is False, doctor_preview
    doctor = provider_doctor(config, project=project, execute=True)
    assert doctor["status"] == "ready" and doctor["verified"] is True, doctor

    receipt = run(
        "semantic-preference",
        "receipt",
        "--surface",
        "issue_fix.pr_description",
        "--application-id",
        "pr-17-description",
        "--outcome",
        "applied",
        "--preference-ref",
        "memory://issue_fix.pr_description",
        "--artifact-ref",
        "https://example.com/pr/17",
    )
    assert receipt["preference_ref_digests"], receipt
    assert "memory://" not in json.dumps(receipt), receipt
    assert not list(project.rglob("*receipt*")), "receipt must remain stateless"

    disabled = temp / "disabled.json"
    disabled.write_text(
        json.dumps(
            {"schema_version": "semantic_preference_hook_config_v0", "enabled": False}
        ),
        encoding="utf-8",
    )
    result = recall_cli(project, disabled, "other_module.summary", execute=True)
    assert result["status"] == "disabled", result

    failing = temp / "failing.json"
    failing_payload = {
        "schema_version": "semantic_preference_hook_config_v0",
        "enabled": True,
        "provider": {"argv": [sys.executable, "-c", "raise SystemExit(7)"]},
        "surfaces": {"other_module.summary": {"query": "preferences"}},
    }
    failing.write_text(json.dumps(failing_payload), encoding="utf-8")
    unavailable = recall(
        failing, project=project, surface="other_module.summary", execute=True
    )
    assert unavailable["status"] == "provider_unavailable", unavailable
    failing_payload["surfaces"]["other_module.summary"]["failure_policy"] = (
        "fail_closed"
    )
    failing.write_text(json.dumps(failing_payload), encoding="utf-8")
    try:
        recall(failing, project=project, surface="other_module.summary", execute=True)
    except ValueError as exc:
        assert "provider unavailable" in str(exc), exc
    else:
        raise AssertionError("fail_closed must stop the caller")

    missing = temp / "missing.json"
    missing.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {
                    "id": "missing_fixture",
                    "argv": ["definitely-missing-semantic-provider"],
                    "setup_hints": {"install": "Install it explicitly."},
                },
                "surfaces": {"other_module.summary": {"query": "preferences"}},
            }
        ),
        encoding="utf-8",
    )
    missing_doctor = provider_doctor(missing, project=project)
    assert missing_doctor["status"] == "provider_missing", missing_doctor
    assert missing_doctor["setup_hints"]["install"] == "Install it explicitly."
    missing_recall = recall(
        missing, project=project, surface="other_module.summary", execute=True
    )
    assert missing_recall["status"] == "provider_unavailable", missing_recall

    invalid_context = run_failure(
        "semantic-preference",
        "recall",
        "--project",
        str(project),
        "--config",
        str(config),
        "--surface",
        "issue_fix.pr_description",
        "--context",
        "not-a-key-value",
    )
    assert invalid_context["status"] == "invalid_request", invalid_context
    assert "lower-snake key=value" in invalid_context["error"], invalid_context

    try:
        application_receipt(
            surface="other_module.summary",
            application_id="bounded-receipt",
            outcome="applied",
            preference_refs=[f"memory://{index}" for index in range(21)],
        )
    except ValueError as exc:
        assert "at most 20" in str(exc), exc
    else:
        raise AssertionError("receipt references must stay bounded")

print("semantic preference hook smoke: ok")
