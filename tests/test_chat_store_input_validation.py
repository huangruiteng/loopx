import json
from pathlib import Path

import pytest

from loopx.chat_store import CHAT_SESSION_SCHEMA_VERSION, ChatSessionStore


def test_session_id_cannot_escape_sessions_directory(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    (store.root / "session.json").write_text(
        json.dumps(
            {
                "schema_version": CHAT_SESSION_SCHEMA_VERSION,
                "session_id": "outside-sessions",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="session_id"):
        store.load_session("..")
