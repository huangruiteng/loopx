from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from loopx.extensions.execution_envelope import (
    EXTENSION_EXECUTION_ENVELOPE_SCHEMA_VERSION,
    build_extension_execution_envelope,
    validate_extension_execution_envelope,
)


REQUEST = {
    "schema_version": "example_request_v0",
    "context": {"target": "example"},
    "execute": True,
}
EXPECTED = {
    "action": "example.record.write",
    "scope": {"target": "example"},
    "extension_id": "example-extension",
    "extension_revision": "revision-1",
    "request": REQUEST,
}


def _envelope(**overrides: Any) -> dict[str, Any]:
    return build_extension_execution_envelope(**{**EXPECTED, **overrides})


def _validate(
    envelope: dict[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    return validate_extension_execution_envelope(
        envelope,
        **{**EXPECTED, **overrides},
    )


def test_execution_envelope_binds_exact_operation() -> None:
    envelope = _validate(_envelope())

    assert envelope == {
        "schema_version": EXTENSION_EXECUTION_ENVELOPE_SCHEMA_VERSION,
        "action": "example.record.write",
        "scope": {"target": "example"},
        "extension": {"id": "example-extension", "revision": "revision-1"},
        "request_digest": envelope["request_digest"],
    }
    assert str(envelope["request_digest"]).startswith("sha256:")


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("action", "example.record.delete", "action does not match"),
        ("scope", {"target": "other"}, "scope does not match"),
        (
            "scope",
            {"target": "example", "extra": "wider"},
            "scope does not match",
        ),
        ("extension_revision", "revision-2", "extension does not match"),
        (
            "request",
            {**REQUEST, "context": {"target": "other"}},
            "request_digest does not match",
        ),
    ],
)
def test_execution_envelope_rejects_operation_rebinding(
    field: str,
    value: object,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        _validate(_envelope(), **{field: value})


def test_execution_envelope_rejects_unknown_fields() -> None:
    envelope = deepcopy(_envelope())
    envelope["issuer"] = "not-part-of-the-contract"

    with pytest.raises(ValueError, match="fields do not match the schema"):
        _validate(envelope)
