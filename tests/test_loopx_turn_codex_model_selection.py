from __future__ import annotations

from pathlib import Path

import pytest

from loopx.control_plane.turn_driver.codex_model_selection import (
    resolve_auto_codex_model_selection,
)


def test_auto_model_selection_uses_available_qualified_pair(tmp_path: Path) -> None:
    codex = tmp_path / "codex"
    codex.write_text(
        """#!/usr/bin/env python3
import json
print(json.dumps({"models": [
    {"slug": "gpt-5.6-luna"},
    {"slug": "gpt-5.6-sol"}
]}))
""",
        encoding="utf-8",
    )
    codex.chmod(0o755)

    selection = resolve_auto_codex_model_selection(codex)

    assert selection == {
        "schema_version": "loopx_turn_model_selection_v0",
        "requested_mode": "auto",
        "profile_id": "codex-sol-luna-v1",
        "advisor_model": "gpt-5.6-sol",
        "executor_model": "gpt-5.6-luna",
        "selection_reason": "highest_priority_available_qualified_pair",
    }


def test_auto_model_selection_fails_closed_when_catalog_is_unavailable(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="codex_advisor_auto_catalog_unavailable"):
        resolve_auto_codex_model_selection(tmp_path / "missing-codex")


def test_auto_model_selection_fails_closed_without_a_complete_qualified_pair(
    tmp_path: Path,
) -> None:
    codex = tmp_path / "codex"
    codex.write_text(
        """#!/usr/bin/env python3
import json
print(json.dumps({"models": [{"slug": "gpt-5.6-sol"}]}))
""",
        encoding="utf-8",
    )
    codex.chmod(0o755)

    with pytest.raises(
        ValueError,
        match="codex_advisor_auto_no_qualified_model_pair",
    ):
        resolve_auto_codex_model_selection(codex)


def test_auto_model_selection_fails_closed_for_malformed_catalog(
    tmp_path: Path,
) -> None:
    codex = tmp_path / "codex"
    codex.write_text("#!/usr/bin/env python3\nprint('not-json')\n", encoding="utf-8")
    codex.chmod(0o755)

    with pytest.raises(ValueError, match="codex_advisor_auto_catalog_unavailable"):
        resolve_auto_codex_model_selection(codex)
