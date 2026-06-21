#!/usr/bin/env python3
"""Smoke-test the Codex CLI active-user simulator contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FORBIDDEN_TEXT = [
    "/" + "Users/",
    ".local/" + "benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth" + ".json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 24000, len(text)


def run_cli_json(args: list[str], *, check: bool = True) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def simulator_output(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "loopx_active_user_simulator_output_v0",
        "simulator_kind": "codex_cli",
        "trigger": "public_progress_or_stall_signal",
        "message": (
            "Reproduce the public failure first, then verify the compiled "
            "extensions and dependency versions before broad edits."
        ),
        "visible_evidence_basis": [
            "public task prompt visible to worker",
            "compact LoopX status and run metadata",
        ],
        "no_oracle_audit": {
            "hidden_tests_visible": False,
            "expected_solution_visible": False,
            "benchmark_answer_key_visible": False,
            "credential_values_visible": False,
            "private_material_visible": False,
            "solution_patch_visible": False,
        },
        "controller_authored_message": False,
    }
    payload.update(overrides)
    return payload


def assert_contract(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert (
        payload["schema_version"]
        == "loopx_active_user_codex_cli_simulator_contract_v0"
    ), payload
    assert payload["simulator_kind"] == "codex_cli", payload
    assert payload["manual_controller_feed_allowed"] is False, payload
    assert payload["codex_cli"]["codex_bin"] == "/opt/homebrew/bin/codex", payload
    assert "codex exec" in payload["codex_cli"]["exec_command"], payload
    assert "active-user-simulator-output" in payload["append_validated_output_command"], payload
    boundary = payload["claim_boundary"]
    assert boundary["direct_codex_chat_injection"] is False, payload
    assert boundary["controller_authored_feed_allowed"] is False, payload
    schema = payload["simulator_output_contract"]["json_schema"]
    assert schema["properties"]["simulator_kind"]["const"] == "codex_cli", schema
    assert_public_safe(payload)


def assert_intervention(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "loopx_active_user_intervention_v0", payload
    assert payload["channel"] == "codex_cli_user_simulator", payload
    assert payload["simulator_kind"] == "codex_cli", payload
    assert payload["formal_treatment_eligible"] is True, payload
    assert payload["manual_controller_feed"] is False, payload
    assert payload["controller_authored_message"] is False, payload
    assert payload["oracle_free"] is True, payload
    assert not any(payload["no_oracle_audit"].values()), payload
    assert_public_safe(payload)


def main() -> int:
    from loopx.worker_bridge import (
        build_active_user_codex_simulator_contract,
        build_active_user_intervention_from_simulator_output,
        observe_active_user_intervention_feed,
    )

    assert_contract(build_active_user_codex_simulator_contract())
    assert_contract(
        run_cli_json(
            [
                "worker-bridge",
                "active-user-codex-simulator-contract",
                "--format",
                "json",
            ]
        )
    )

    intervention = build_active_user_intervention_from_simulator_output(
        seq=3,
        simulator_output=simulator_output(),
    )
    assert_intervention(intervention)

    with tempfile.TemporaryDirectory(prefix="active-user-codex-simulator-") as tmp:
        root = Path(tmp)
        output_path = root / "simulator-output.json"
        feed_path = root / "feed.jsonl"
        output_path.write_text(json.dumps(simulator_output()), encoding="utf-8")
        cli_intervention = run_cli_json(
            [
                "worker-bridge",
                "active-user-simulator-output",
                "--seq",
                "4",
                "--simulator-output-json",
                str(output_path),
                "--format",
                "json",
            ]
        )
        assert_intervention(cli_intervention)

        jsonl = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "worker-bridge",
                "active-user-simulator-output",
                "--seq",
                "5",
                "--simulator-output-json",
                str(output_path),
                "--jsonl",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        ).stdout.strip()
        feed_path.write_text(jsonl + "\n", encoding="utf-8")
        observed = observe_active_user_intervention_feed(feed_path, worker_start_seq=4)
        latest = observed["latest_intervention"]
        assert latest["simulator_kind"] == "codex_cli", observed
        assert latest["formal_treatment_eligible"] is True, observed
        assert latest["manual_controller_feed"] is False, observed
        assert_public_safe(observed)

        rejected_controller = simulator_output(controller_authored_message=True)
        output_path.write_text(json.dumps(rejected_controller), encoding="utf-8")
        rejected = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "worker-bridge",
                "active-user-simulator-output",
                "--seq",
                "6",
                "--simulator-output-json",
                str(output_path),
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert rejected.returncode == 1, rejected.stdout
        rejected_payload = json.loads(rejected.stdout)
        assert "controller-authored" in rejected_payload["error"], rejected_payload

        rejected_oracle = simulator_output()
        rejected_oracle["no_oracle_audit"]["hidden_tests_visible"] = True
        output_path.write_text(json.dumps(rejected_oracle), encoding="utf-8")
        rejected = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "worker-bridge",
                "active-user-simulator-output",
                "--seq",
                "7",
                "--simulator-output-json",
                str(output_path),
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert rejected.returncode == 1, rejected.stdout
        rejected_payload = json.loads(rejected.stdout)
        assert "no-oracle audit" in rejected_payload["error"], rejected_payload

        rejected_extra = simulator_output(secret_hint="should be rejected")
        output_path.write_text(json.dumps(rejected_extra), encoding="utf-8")
        rejected = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "worker-bridge",
                "active-user-simulator-output",
                "--seq",
                "8",
                "--simulator-output-json",
                str(output_path),
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert rejected.returncode == 1, rejected.stdout
        rejected_payload = json.loads(rejected.stdout)
        assert "unsupported fields" in rejected_payload["error"], rejected_payload

    print("active-user-codex-simulator-contract-smoke ok formal_treatment=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
