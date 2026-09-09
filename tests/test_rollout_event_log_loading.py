from __future__ import annotations

from pathlib import Path

import loopx.rollout_event_log as rollout_event_log


def test_limited_rollout_event_load_keeps_only_a_bounded_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class TrackedEvent(dict[str, int]):
        alive = 0
        peak = 0

        def __init__(self, index: int) -> None:
            super().__init__(index=index)
            type(self).alive += 1
            type(self).peak = max(type(self).peak, type(self).alive)

        def __del__(self) -> None:
            type(self).alive -= 1

    monkeypatch.setattr(
        rollout_event_log,
        "iter_rollout_events",
        lambda _path: (TrackedEvent(index) for index in range(100)),
    )

    events = rollout_event_log.load_rollout_events(tmp_path / "unused", limit=3)

    assert [event["index"] for event in events] == [97, 98, 99]
    assert TrackedEvent.peak <= 4
