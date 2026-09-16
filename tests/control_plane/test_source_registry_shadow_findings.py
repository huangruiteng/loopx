"""Refs #4447 (Track A): one definition for the source-registry shadow vocabulary.

`SOURCE_REGISTRY_SHADOW_FINDINGS` used to be defined in two active modules with
identical values, feeding the same `source_registry_shadow_findings` parameter of
the attention-queue read model. Classifying that fork as `same_semantics` made it
merge work: the control_plane projection now owns the only definition and
`loopx.status` re-exports it, so the two copies can no longer drift apart.

`loopx.status` keeps re-exporting the name because
`examples/control_plane/attention-queue-readmodel-smoke.py` reads it as
`status_module.SOURCE_REGISTRY_SHADOW_FINDINGS`.
"""

from __future__ import annotations

import inspect

from loopx import status
from loopx.control_plane.status import registry_health_projection

EXPECTED_FINDINGS = {"source_registry_missing", "stale_source_registry"}


def test_vocabulary_is_unchanged() -> None:
    """Merging the fork must not change the admitted values."""
    assert (
        set(registry_health_projection.SOURCE_REGISTRY_SHADOW_FINDINGS)
        == EXPECTED_FINDINGS
    )


def test_status_shares_the_single_definition() -> None:
    """`loopx.status` re-exports the projection's set instead of owning a copy."""
    assert (
        status.SOURCE_REGISTRY_SHADOW_FINDINGS
        is registry_health_projection.SOURCE_REGISTRY_SHADOW_FINDINGS
    )


def test_status_defines_no_second_copy() -> None:
    """A literal reintroduced into `loopx.status` would fork the vocabulary again."""
    assert "stale_source_registry" not in inspect.getsource(status)
