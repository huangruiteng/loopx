"""Actual Python -> managed TS -> File readback, without an active Goal."""
from pathlib import Path

import pytest

from loopx.control_plane.coordination.local_authority_shadow_adapter import (
    read_local_authority_shadow,
)


@pytest.mark.parametrize("cursor", [None, "1", "9007199254740993"])
def test_empty_journal_checkpoint_survives_runtime_transport(tmp_path: Path, cursor: str | None) -> None:
    root = tmp_path / "runtime"
    directory = root / "authority-shadow" / "file" / "synthetic-journal"
    directory.mkdir(parents=True)
    identity = directory / "store-identity"
    identity.write_text("file:" + "a" * 32, encoding="ascii")
    before = identity.read_bytes()

    result = read_local_authority_shadow(
        runtime_root=root, goal_id="synthetic-journal", store_kind="legacy_observation",
        scan_after_cursor=cursor, scan_limit=1,
    )

    if cursor is None:
        assert result["status"] == "missing"
        assert result["scan"] == {"transactions": [], "next_cursor": None, "has_more": False}
    else:
        assert result["status"] == "failed"
        assert result["reason_code"] == "scan_cursor_out_of_range"
        assert result["scan"] is None
    assert identity.read_bytes() == before
    assert sorted(path.name for path in directory.iterdir()) == ["store-identity"]
