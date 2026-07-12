from __future__ import annotations

import json
from typing import Any

import pytest

from loopx.canary.runner import build_canary_smoke_suite_run, run_canary_smoke_check


def _option_list(config: Any, name: str) -> list[str]:
    values = config.getoption(name) or []
    items: list[str] = []
    for value in values:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                items.append(item)
    return items


def _build_preview(config: Any) -> dict[str, Any]:
    return build_canary_smoke_suite_run(
        suite=str(config.getoption("loopx_smoke_suite") or "default-public"),
        modules=_option_list(config, "loopx_smoke_modules"),
        exclude_modules=_option_list(config, "loopx_smoke_exclude_modules"),
        scripts=_option_list(config, "loopx_smoke_scripts"),
        families=_option_list(config, "loopx_smoke_families"),
        profiles=_option_list(config, "loopx_smoke_profiles"),
        include_deep_checks=bool(config.getoption("loopx_smoke_include_deep_checks")),
        offset=int(config.getoption("loopx_smoke_offset") or 0),
        limit=int(config.getoption("loopx_smoke_limit") or 0),
        execute=False,
        timeout_seconds=float(config.getoption("loopx_smoke_timeout") or 120.0),
    )


def _smoke_suite_requested(config: Any) -> bool:
    return bool(
        config.getoption("loopx_smoke_suite")
        or _option_list(config, "loopx_smoke_modules")
        or _option_list(config, "loopx_smoke_exclude_modules")
        or _option_list(config, "loopx_smoke_scripts")
        or _option_list(config, "loopx_smoke_profiles")
        or _option_list(config, "loopx_smoke_families")
        or config.getoption("loopx_smoke_include_deep_checks")
    )


def _preview(config: Any) -> dict[str, Any]:
    cached = getattr(config, "_loopx_smoke_suite_preview", None)
    if isinstance(cached, dict):
        return cached
    payload = _build_preview(config)
    setattr(config, "_loopx_smoke_suite_preview", payload)
    return payload


def _check_id(check: dict[str, Any]) -> str:
    normalized = (
        check.get("normalized") if isinstance(check.get("normalized"), dict) else {}
    )
    script = normalized.get("script") or check.get("command") or "smoke"
    return str(script).removeprefix("examples/").replace("/", "__")


def _format_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _format_result(result: dict[str, Any]) -> str:
    normalized = (
        result.get("normalized") if isinstance(result.get("normalized"), dict) else {}
    )
    lines = [
        f"command: {' '.join(str(part) for part in normalized.get('display_argv') or [])}",
        f"status: {result.get('status')}",
        f"returncode: {result.get('returncode')}",
        f"duration_seconds: {result.get('duration_seconds')}",
    ]
    if result.get("reason"):
        lines.append(f"reason: {result.get('reason')}")
    if result.get("stdout_tail"):
        lines.extend(["stdout_tail:", str(result.get("stdout_tail")).rstrip()])
    if result.get("stderr_tail"):
        lines.extend(["stderr_tail:", str(result.get("stderr_tail")).rstrip()])
    return "\n".join(lines)


def pytest_generate_tests(metafunc: Any) -> None:
    if "smoke_check" not in metafunc.fixturenames:
        return
    if not _smoke_suite_requested(metafunc.config):
        metafunc.parametrize("smoke_check", [])
        return
    payload = _preview(metafunc.config)
    checks = [
        check for check in payload.get("selected_checks", []) if isinstance(check, dict)
    ]
    metafunc.parametrize(
        "smoke_check", checks, ids=[_check_id(check) for check in checks]
    )


def test_smoke_suite_selection_contract(pytestconfig: Any) -> None:
    if not _smoke_suite_requested(pytestconfig):
        pytest.skip("canary smoke-suite facade is opt-in")
    payload = _preview(pytestconfig)
    assert payload["schema_version"] == "canary_smoke_suite_run_v0", _format_payload(
        payload
    )
    assert payload["executes_checks"] is False, _format_payload(payload)
    assert payload["writes_evidence"] is False, _format_payload(payload)
    assert payload["warning_count"] == 0, _format_payload(payload)
    assert payload["unsafe_command_count"] == 0, _format_payload(payload)
    assert payload["selected_check_count"] > 0, _format_payload(payload)
    assert payload["ok"] is True, _format_payload(payload)


def test_smoke_suite_script(smoke_check: dict[str, Any], pytestconfig: Any) -> None:
    result = run_canary_smoke_check(
        smoke_check,
        timeout_seconds=float(pytestconfig.getoption("loopx_smoke_timeout") or 120.0),
    )
    assert result.get("ok") is True, _format_result(result)
