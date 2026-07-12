#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.lark.event_inbox import (  # noqa: E402
    acknowledge_lark_event_inbox,
    ingest_lark_event_inbox,
    inspect_lark_event_inbox,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as raw:
        project = Path(raw)
        inbox = project / ".loopx" / "inbox" / "team-feedback"
        config = project / ".loopx" / "config" / "lark-event-inbox.json"
        inbox.mkdir(parents=True)
        config.parent.mkdir(parents=True)
        config.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": ".loopx/inbox/team-feedback",
                }
            ),
            encoding="utf-8",
        )
        event = {
            "schema_version": "lark_event_inbox_event_v0",
            "event_id": "evt-review-1",
            "message_id": "om_review_1",
            "create_time": "2026-07-12T10:00:00Z",
            "content": "@LoopX Bot please record this feedback for the owning domain",
        }
        (inbox / "evt-review-1.json").write_text(json.dumps(event), encoding="utf-8")
        (inbox / "duplicate.json").write_text(
            json.dumps({**event, "event_id": "evt-review-1-retry"}),
            encoding="utf-8",
        )
        (inbox / "invalid.json").write_text("{}", encoding="utf-8")

        pending = inspect_lark_event_inbox(
            project=project,
            config_path=config,
        )
        assert pending["pending_count"] == 1, pending
        assert pending["invalid_count"] == 1, pending
        assert pending["items"][0]["message_id"] == "om_review_1", pending
        assert pending["thread_complete"] is False, pending
        assert "thread replies" in pending["coverage_warning"], pending

        config.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": ".loopx/inbox/team-feedback",
                    "capture_scope": "configured_chat_all",
                }
            ),
            encoding="utf-8",
        )
        pending = inspect_lark_event_inbox(project=project, config_path=config)
        assert pending["thread_complete"] is True, pending

        imported = ingest_lark_event_inbox(
            project=project,
            config_path=config,
            events=[
                {
                    "schema_version": "lark_event_inbox_event_v0",
                    "event_id": "evt-thread-reply-2",
                    "message_id": "om_review_2",
                    "create_time": "2026-07-12T10:01:00Z",
                    "content": "A thread reply without a direct bot mention",
                },
                event,
                {"schema_version": "wrong"},
            ],
            execute=True,
        )
        assert imported["accepted_count"] == 1, imported
        assert imported["duplicate_count"] == 1, imported
        assert imported["invalid_count"] == 1, imported
        assert (
            inspect_lark_event_inbox(
                project=project,
                config_path=config,
            )["pending_count"]
            == 2
        )

        preview = acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_1"],
        )
        assert preview["write_performed"] is False, preview

        written = acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_1"],
            execute=True,
        )
        assert written["write_performed"] is True, written
        assert (
            inspect_lark_event_inbox(
                project=project,
                config_path=config,
            )["pending_count"]
            == 1
        )

        acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_2"],
            execute=True,
        )

        repeated = acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_1"],
            execute=True,
        )
        assert repeated["write_performed"] is False, repeated

        processed = json.loads((inbox / "processed.json").read_text(encoding="utf-8"))
        assert processed["schema_version"] == "lark_event_inbox_processed_v0"

        outside = project / ".loopx" / "config" / "outside.json"
        outside.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": "../outside",
                }
            ),
            encoding="utf-8",
        )
        try:
            inspect_lark_event_inbox(project=project, config_path=outside)
        except ValueError as exc:
            assert ".loopx/inbox" in str(exc)
        else:
            raise AssertionError("unsafe inbox path must fail closed")

    print("lark-event-inbox-smoke: ok")


if __name__ == "__main__":
    main()
