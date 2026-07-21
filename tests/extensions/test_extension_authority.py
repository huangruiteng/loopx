from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from loopx.extensions.authority import (
    EXTENSION_AUTHORITY_DECISION_SCHEMA_VERSION,
    build_extension_authority_decision,
    validate_extension_authority_decision,
)


NOW = datetime(2026, 7, 21, 8, 0, tzinfo=timezone.utc)
REQUEST = {
    "schema_version": "example_request_v0",
    "context": {"target": "example"},
    "execute": True,
}
EXPECTED = {
    "capability_id": "example-capability",
    "protocol": "example_provider_v0",
    "permission": "example.write",
    "action": "example.record.write",
    "scope": {"target": "example"},
    "extension_id": "example-extension",
    "extension_revision": "revision-1",
    "request": REQUEST,
}


def _decision(**overrides: Any) -> dict[str, Any]:
    kwargs = {**EXPECTED, "now": NOW, **overrides}
    return build_extension_authority_decision(**kwargs)


def _validate(
    decision: dict[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    kwargs = {**EXPECTED, "now": NOW + timedelta(seconds=1), **overrides}
    return validate_extension_authority_decision(decision, **kwargs)


def test_typed_extension_authority_binds_exact_operation() -> None:
    decision = _decision()

    validated = _validate(decision)

    assert validated["schema_version"] == EXTENSION_AUTHORITY_DECISION_SCHEMA_VERSION
    assert validated["decision"] == "allow"
    assert validated["issuer"] == {
        "kind": "capability",
        "capability_id": "example-capability",
    }
    assert validated["extension"] == {
        "id": "example-extension",
        "revision": "revision-1",
    }
    assert str(validated["decision_id"]).startswith("extauth_")


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("permission", "example.read", "permission does not match"),
        ("action", "example.record.delete", "action does not match"),
        ("scope", {"target": "other"}, "scope does not match"),
        ("extension_revision", "revision-2", "extension does not match"),
        (
            "request",
            {**REQUEST, "context": {"target": "other"}},
            "request_digest does not match",
        ),
    ],
)
def test_typed_extension_authority_rejects_operation_rebinding(
    field: str,
    value: object,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        _validate(_decision(), **{field: value})


def test_typed_extension_authority_rejects_tampering_and_expiry() -> None:
    tampered = deepcopy(_decision())
    tampered["decision_id"] = "extauth_tampered"
    with pytest.raises(ValueError, match="decision_id does not match"):
        _validate(tampered)

    expired = _decision(now=NOW - timedelta(minutes=10))
    with pytest.raises(ValueError, match="has expired"):
        _validate(expired)


def test_typed_extension_authority_caps_lifetime() -> None:
    with pytest.raises(ValueError, match="between 1 and 300"):
        _decision(lifetime_seconds=301)


def test_typed_extension_authority_rejects_unknown_fields() -> None:
    decision = _decision()
    decision["untyped_hint"] = "ignore-authority"

    with pytest.raises(ValueError, match="fields do not match the schema"):
        _validate(decision)
