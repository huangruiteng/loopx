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
    maintenance_receipt,
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
    "items": [{
        "preference_ref": f"memory://{surface}",
        "summary": f"prefer {surface}",
    }],
    "corpus_inventory": [{
        "corpus_id": "fixture_preferences",
        "scope_ref": "memory://fixture/preferences",
        "read_role": "primary",
        "write_mode": "provider_managed",
        "write_actor_ref": "fixture-peer",
        "source_of_truth": "explicit_user_feedback",
        "writeback_triggers": ["explicit_feedback"],
        "closure_policy": "write_wait_l2_read_scoped_recall",
    }],
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
        assert recalled["corpus_inventory"][0]["corpus_id"] == (
            "fixture_preferences"
        ), recalled
        assert recalled["maintenance_guidance"] == {
            "schema_version": "semantic_preference_maintenance_guidance_v0",
            "corpus_ids": ["fixture_preferences"],
            "writeback_triggers": ["explicit_feedback"],
            "closure_outcomes": ["verified", "no_write_rationale"],
            "completion": "provider_write_then_wait_l2_read_and_scoped_recall",
        }, recalled

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

    maintenance = run(
        "semantic-preference",
        "maintenance-receipt",
        "--trigger",
        "explicit_feedback",
        "--outcome",
        "verified",
        "--corpus-id",
        "fixture_preferences",
        "--scope-ref",
        "memory://fixture/preferences",
        "--evidence-ref",
        "fixture-readback-v1",
    )
    assert maintenance["schema_version"] == (
        "semantic_preference_maintenance_receipt_v0"
    ), maintenance
    assert maintenance["scope_ref_digests"], maintenance
    assert "memory://" not in json.dumps(maintenance), maintenance
    assert maintenance_receipt(
        trigger="source_truth_changed",
        outcome="no_write_rationale",
        corpus_ids=["fixture_preferences"],
    )["outcome"] == "no_write_rationale"
    try:
        maintenance_receipt(
            trigger="explicit_feedback",
            outcome="verified",
            corpus_ids=["fixture_preferences"],
            scope_refs=["not a public-safe scope"],
        )
    except ValueError as exc:
        assert "public-safe" in str(exc), exc
    else:
        raise AssertionError("maintenance scope references must stay bounded")

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

    invalid_provider = temp / "invalid-provider.py"
    invalid_provider.write_text(
        """import json, sys
json.load(sys.stdin)
json.dump({
    "schema_version": "semantic_preference_provider_response_v0",
    "items": [],
    "corpus_inventory": [{"corpus_id": "INVALID"}],
}, sys.stdout)
""",
        encoding="utf-8",
    )
    invalid_inventory = temp / "invalid-inventory.json"
    invalid_inventory.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {"argv": [sys.executable, str(invalid_provider)]},
                "surfaces": {"other_module.summary": {"query": "preferences"}},
            }
        ),
        encoding="utf-8",
    )
    invalid_recall = recall(
        invalid_inventory,
        project=project,
        surface="other_module.summary",
        execute=True,
    )
    assert invalid_recall["failure_kind"] == "invalid_corpus_inventory", (
        invalid_recall
    )

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
