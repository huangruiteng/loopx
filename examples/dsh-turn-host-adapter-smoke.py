"""Smoke for the thin DeepSeek Harness Turn host adapter.

Guards the reusable request/result translation without calling a model or the
network: signed authority extraction from the bounded Turn envelope, parsing of
the dsh final-message JSON candidate, result shaping, and acceptance by the
real LoopX host-result validator.
"""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
for path in (str(REPO_ROOT), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

# The generic-cli e2e smoke owns the fake runner source every host smoke reuses,
# because a fake runner whose keyword signature lags the adapter turns into an
# unattributed ``host_failure`` instead of naming the seam that moved.
_BASE_PATH = REPO_ROOT / "examples" / "loopx-turn-dsh-e2e-smoke.py"
_SPEC = importlib.util.spec_from_file_location("loopx_turn_dsh_e2e_smoke", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_base = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _base
_SPEC.loader.exec_module(_base)

import dsh_turn_host_adapter as adapter  # noqa: E402
from loopx.control_plane.turn_driver.executor import (  # noqa: E402
    validate_loopx_turn_host_result,
)
from loopx.control_plane.quota.turn_envelope import (  # noqa: E402
    turn_envelope_action_signature_document,
)


TURN_KEY = "sha256:" + "0" * 64


def _request(
    *,
    recommended_action: str = "Do the small thing.",
    primary_action: str = "Do the signed thing.",
) -> dict:
    request = {
        "schema_version": adapter.LOOPX_TURN_HOST_REQUEST_SCHEMA,
        "turn_key": TURN_KEY,
        "route": "primary_delivery",
        "session": {"goal_id": "g", "agent_id": "a"},
        "turn_envelope": {
            "schema_version": "loopx_turn_envelope_v0",
            "goal_id": "g",
            "agent_id": "a",
            "action": {
                "recommended_action": recommended_action,
                "primary_action": primary_action,
                "must_attempt": True,
            },
            "required_reads": [
                {
                    "kind": "command",
                    "command": "git status --short",
                    "reason": "establish the workspace baseline",
                }
            ],
            "boundary": {
                "write_scope": ["docs/**", "tests/**"],
                "workspace_guard": {
                    "schema_version": "workspace_guard_v0",
                    "status": "ready",
                    "action": "continue",
                },
            },
            "action_signature": {
                "schema_version": "loopx_action_signature_v0",
                "matches": True,
            },
        },
        "result_contract": {
            "schema_version": adapter.LOOPX_TURN_RESULT_SCHEMA,
            "completed_phases": list(adapter.COMPLETED_PHASES),
        },
    }
    signature = turn_envelope_action_signature_document(request["turn_envelope"])
    signature_hash = "sha256:" + sha256(
        json.dumps(
            signature,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    request["turn_envelope"]["action_signature"].update(
        {
            "source_hash": signature_hash,
            "envelope_hash": signature_hash,
        }
    )
    return request


def _plan(request: dict) -> dict:
    return {
        "transaction": {"turn_key": request["turn_key"]},
        "turn_envelope": request["turn_envelope"],
    }


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_action_text_uses_signed_primary_action() -> None:
    request = _request(
        recommended_action="legacy action must not win",
        primary_action="signed primary action",
    )
    _assert(
        adapter.extract_action_text(request) == "signed primary action",
        "signed primary_action must be the bounded task body",
    )


def test_unsigned_action_is_rejected() -> None:
    request = _request()
    request["turn_envelope"]["action_signature"]["matches"] = False
    try:
        adapter.extract_action_text(request)
    except ValueError as exc:
        _assert("action signature" in str(exc), "signature error must be actionable")
    else:  # pragma: no cover - defensive
        raise AssertionError("unsigned TurnEnvelope action must fail closed")


def test_action_tampering_after_signature_is_rejected() -> None:
    request = _request()
    request["turn_envelope"]["action"]["primary_action"] = "tampered action"
    try:
        adapter.extract_action_text(request)
    except ValueError as exc:
        _assert("action signature" in str(exc), "tamper error must be actionable")
    else:  # pragma: no cover - defensive
        raise AssertionError("post-signature TurnEnvelope tampering must fail closed")


def test_prompt_preserves_structured_turn_authority() -> None:
    request = _request(recommended_action="legacy action must not appear")
    authority = adapter.extract_turn_authority(request)
    prompt = adapter.render_prompt(authority)
    _assert(
        authority["primary_action"] == "Do the signed thing.",
        "primary_action must be preserved",
    )
    _assert(
        authority["required_reads"] == request["turn_envelope"]["required_reads"],
        "required_reads must be preserved without prose reconstruction",
    )
    _assert(
        authority["write_scope"] == ["docs/**", "tests/**"],
        "the complete write scope must be preserved",
    )
    _assert(
        authority["workspace_guard"]
        == request["turn_envelope"]["boundary"]["workspace_guard"],
        "the complete workspace guard must be preserved",
    )
    _assert("legacy action must not appear" not in prompt, "legacy action must not leak")
    for expected in (
        '"primary_action":"Do the signed thing."',
        '"command":"git status --short"',
        '"write_scope":["docs/**","tests/**"]',
        '"workspace_guard":{"action":"continue"',
        "- recommended_action:",
        "- vision_unchanged_reason:",
    ):
        _assert(expected in prompt, f"prompt must contain structured authority: {expected}")


def test_parse_model_json_accepts_exact_and_fenced_json() -> None:
    candidate = {
        "result_kind": "validated_progress",
        "classification": "updated config",
        "recommended_action": "review",
        "next_action": "run the smoke",
        "vision_unchanged_reason": "the objective is unchanged",
        "summary": "changed one field",
    }
    encoded = json.dumps(candidate)
    _assert(adapter.parse_model_json(encoded) == candidate, "exact JSON must parse")
    _assert(
        adapter.parse_model_json("```json\n" + encoded + "\n```") == candidate,
        "fenced JSON must parse",
    )
    _assert(
        adapter.parse_model_json("Here is the result:\n" + encoded + "\nDone") == candidate,
        "JSON embedded in prose must parse",
    )
    _assert(adapter.parse_model_json("not json") is None, "invalid output must fail closed")


def test_material_progress_result_validates() -> None:
    request = _request()
    candidate = {
        "result_kind": "validated_progress",
        "classification": "single surface change",
        "summary": "edited one file",
        "next_action": "review the diff",
    }
    result = adapter.build_result(request, candidate)
    verdict = validate_loopx_turn_host_result(_plan(request), result)
    _assert(verdict["ok"], "material result must validate: " + "; ".join(verdict["errors"]))


def test_wait_result_validates_without_material_fields() -> None:
    request = _request()
    result = adapter.build_result(
        request,
        {
            "result_kind": "wait",
            "classification": "throttled",
            "next_action": "retry after cadence",
        },
    )
    verdict = validate_loopx_turn_host_result(_plan(request), result)
    _assert(verdict["ok"], "wait result must validate: " + "; ".join(verdict["errors"]))
    _assert("delivery_batch_scale" not in result, "stop kinds carry no batch scale")


def test_missing_result_block_fails_closed_to_wait() -> None:
    request = _request()
    result = adapter.build_result(request, None, fallback_reason="no block found")
    _assert(result["result_kind"] == "wait", "missing block must not fabricate progress")
    verdict = validate_loopx_turn_host_result(_plan(request), result)
    _assert(verdict["ok"], "fail-closed wait must validate: " + "; ".join(verdict["errors"]))


def test_unsupported_result_kind_fails_closed_to_wait() -> None:
    request = _request()
    result = adapter.build_result(
        request,
        {"result_kind": "not_a_loopx_kind", "summary": "bad"},
    )
    _assert(result["result_kind"] == "wait", "unsupported kind must not fabricate progress")
    _assert(
        result["classification"] == "unsupported_host_result_kind",
        "unsupported kind must be labeled",
    )
    verdict = validate_loopx_turn_host_result(_plan(request), result)
    _assert(verdict["ok"], "unsupported-kind wait must validate: " + "; ".join(verdict["errors"]))


def test_text_fields_are_bounded() -> None:
    request = _request()
    candidate = {
        "result_kind": "user_action_required",
        "classification": "x" * 500,
        "summary": "y" * 900,
        "next_action": "z" * 5000,
    }
    result = adapter.build_result(request, candidate)
    _assert(
        len(result["classification"]) <= 120,
        "classification must respect its limit",
    )
    _assert(len(result["summary"]) <= 400, "summary must respect its limit")
    _assert(len(result["next_action"]) <= 1_200, "next_action must respect its limit")


def test_subprocess_adapter_roundtrip_with_fake_dsh_runner() -> None:
    """End-to-end: request -> fake dsh runner -> typed Turn result."""

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workspace = root / "workspace"
        workspace.mkdir()
        runner = root / "fake_dsh_runner.py"
        marker = root / "prompt.json"
        block = json.dumps(
            {
                "result_kind": "validated_progress",
                "classification": "did it",
                "recommended_action": "review",
                "summary": "one change",
                "next_action": "review",
                "vision_unchanged_reason": "the objective is unchanged",
            }
        )
        runner.write_text(
            "import json, pathlib, sys\n"
            + _base.FAKE_DSH_RUNNER_SIGNATURE
            + f"    pathlib.Path({str(marker)!r}).write_text(prompt, "
            + "encoding='utf-8')\n"
            + f"    return {block!r}\n",
            encoding="utf-8",
        )

        request = _request()
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "dsh_turn_host_adapter.py"),
                "--dsh-runner",
                str(runner),
                "--workspace",
                str(workspace),
            ],
            input=json.dumps(request),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        _assert(completed.returncode == 0, "adapter must exit 0: " + completed.stderr)
        result = json.loads(completed.stdout)
        verdict = validate_loopx_turn_host_result(_plan(request), result)
        _assert(
            verdict["ok"],
            "roundtrip result must validate: " + "; ".join(verdict["errors"]),
        )
        _assert(
            result["result_kind"] == "validated_progress",
            "fake dsh result must carry the material result",
        )
        prompt_text = marker.read_text(encoding="utf-8")
        _assert("Do the signed thing." in prompt_text, "prompt must use signed action")


def main() -> int:
    tests = [
        test_action_text_uses_signed_primary_action,
        test_unsigned_action_is_rejected,
        test_action_tampering_after_signature_is_rejected,
        test_prompt_preserves_structured_turn_authority,
        test_parse_model_json_accepts_exact_and_fenced_json,
        test_material_progress_result_validates,
        test_wait_result_validates_without_material_fields,
        test_missing_result_block_fails_closed_to_wait,
        test_unsupported_result_kind_fails_closed_to_wait,
        test_text_fields_are_bounded,
        test_subprocess_adapter_roundtrip_with_fake_dsh_runner,
    ]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
