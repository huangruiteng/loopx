"""Slot classification for the Decision Context capability ids (Refs #4447).

Track A of #4447 flags ``DECISION_CONTEXT_CAPABILITY_ID`` as a same-name,
different-value fork: ``decision-context`` in ``extension_provider.py`` and
``decision_context`` in ``packets.py``. Checking the callers shows these are
two slots, not a conflict:

* the hyphenated spelling is the extension/catalog/CLI namespace, and it is
  the spelling every ``loopx/capabilities/*/catalog_entry.py`` id uses;
* the underscore spelling is the capability packet contract, and it is the
  spelling the sibling capability emits (``material_lifecycle``).

No consumer joins the two, and each namespace is internally consistent, so
both values are retained. The constants now name their slot; these tests lock
the classification so a later "unification" cannot quietly break either
extension lookup or packet consumers.
"""

from __future__ import annotations

from loopx.capabilities.decision_context.catalog_entry import (
    DECISION_CONTEXT_CATALOG_ENTRY,
)
from loopx.capabilities.decision_context.extension_provider import (
    DECISION_CONTEXT_EXTENSION_CAPABILITY_ID,
)
from loopx.capabilities.decision_context.packets import (
    DECISION_CONTEXT_PACKET_CAPABILITY_ID,
)
from loopx.capabilities.material_lifecycle.catalog_entry import (
    MATERIAL_LIFECYCLE_CATALOG_ENTRY,
)


def test_extension_binding_id_uses_the_hyphenated_catalog_spelling() -> None:
    assert DECISION_CONTEXT_EXTENSION_CAPABILITY_ID == "decision-context"
    assert (
        DECISION_CONTEXT_EXTENSION_CAPABILITY_ID
        == DECISION_CONTEXT_CATALOG_ENTRY["id"]
    )
    assert "_" not in DECISION_CONTEXT_EXTENSION_CAPABILITY_ID


def test_packet_contract_id_uses_the_underscore_spelling() -> None:
    assert DECISION_CONTEXT_PACKET_CAPABILITY_ID == "decision_context"
    assert "-" not in DECISION_CONTEXT_PACKET_CAPABILITY_ID


def test_the_two_slots_are_not_the_same_value() -> None:
    assert (
        DECISION_CONTEXT_PACKET_CAPABILITY_ID
        != DECISION_CONTEXT_EXTENSION_CAPABILITY_ID
    )


def test_sibling_capability_follows_the_same_two_slot_split() -> None:
    """`material-lifecycle` / `material_lifecycle` is the same split.

    The constant pairs differ only in namespace, so the sibling capability is
    the evidence that these are conventions and not one-off drift.
    """
    assert MATERIAL_LIFECYCLE_CATALOG_ENTRY["id"] == "material-lifecycle"
    assert DECISION_CONTEXT_CATALOG_ENTRY["id"] == "decision-context"
