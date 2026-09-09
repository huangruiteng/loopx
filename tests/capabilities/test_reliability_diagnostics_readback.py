from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from loopx.capabilities.reliability_diagnostics import (
    FIXTURE_GOAL_ID,
    append_ledger_records,
    ledger_path,
    run_dsh_fixture,
)


def run_status(runtime, *extra, as_of="2026-09-01T12:02:00+00:00", raw=False):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--runtime-root", str(runtime),
         "--format", "json", "reliability-diagnostics", "status", "--goal-id",
         FIXTURE_GOAL_ID, *(["--as-of", as_of] if as_of is not None else []), *extra],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        check=not raw,
        timeout=30,
    )
    return result if raw else json.loads(result.stdout)


def test_receipt_opt_in_preserves_projection_and_real_ledger(tmp_path):
    path = ledger_path(tmp_path, FIXTURE_GOAL_ID)
    append_ledger_records(path, run_dsh_fixture()["ledger_records"])
    before = path.read_bytes()
    plain = run_status(tmp_path)
    combined = run_status(tmp_path, "--with-receipt")
    assert "receipt" not in plain
    assert combined["projection"] == plain["projection"]
    assert combined["receipt"]["status"] == "degraded"
    assert combined["receipt"]["status"] == combined["projection"]["integrity"]["status"]
    assert combined["projection"]["authority"] == "none"
    assert combined["receipt"]["observation_entered_scheduler_inputs"] is False
    assert path.read_bytes() == before
    assert str(tmp_path) not in json.dumps(combined)


def test_missing_or_corrupt_ledger_never_becomes_healthy(tmp_path):
    absent = run_status(tmp_path, "--with-receipt")
    assert absent["receipt"]["status"] == "invalid"
    path = ledger_path(tmp_path, FIXTURE_GOAL_ID)
    assert not path.exists()
    path.parent.mkdir(parents=True)
    path.write_text("not-json\n", encoding="utf-8")
    corrupt = run_status(tmp_path, "--with-receipt")
    assert corrupt["receipt"]["status"] == "invalid"
    assert corrupt["receipt"]["ledger_invalid_record_count"] == 1
    assert path.read_text(encoding="utf-8") == "not-json\n"


def test_live_as_of_detects_silence_without_changing_integrity(tmp_path):
    path = ledger_path(tmp_path, FIXTURE_GOAL_ID)
    append_ledger_records(path, run_dsh_fixture()["ledger_records"])
    before = path.read_bytes()
    historical = run_status(tmp_path, "--with-receipt", as_of=None)
    live = run_status(tmp_path, "--with-receipt", as_of="2026-09-06T00:00:00+00:00")
    assert historical["projection"]["stall"]["last_event_age_ms"] == 0
    assert historical["projection"]["stall"]["detected"] is False
    assert live["projection"]["stall"]["last_event_age_ms"] > 300000
    assert live["projection"]["stall"]["detected"] is True
    assert live["receipt"] == historical["receipt"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("ledger_state", ["missing", "empty", "corrupt", "events"])
@pytest.mark.parametrize("with_receipt", [False, True])
@pytest.mark.parametrize("as_of,valid", [
    ("2026-09-06T00:00:00Z", True),
    ("2026-09-06T08:00:00+08:00", True),
    ("2026-09-06T00:00:00", False),
    ("not-a-date", False),
    ("", False),
])
def test_explicit_as_of_validation_is_independent_of_ledger(
    tmp_path, ledger_state, with_receipt, as_of, valid,
):
    path = ledger_path(tmp_path, FIXTURE_GOAL_ID)
    if ledger_state == "events":
        append_ledger_records(path, run_dsh_fixture()["ledger_records"])
    elif ledger_state != "missing":
        path.parent.mkdir(parents=True)
        path.write_text("not-json\n" if ledger_state == "corrupt" else "")
    before = path.read_bytes() if path.exists() else None
    result = run_status(
        tmp_path, *(["--with-receipt"] if with_receipt else []),
        as_of=as_of, raw=True,
    )
    assert result.returncode == (0 if valid else 2)
    assert "Traceback" not in result.stderr
    if valid:
        payload = json.loads(result.stdout)
        assert ("receipt" in payload) is with_receipt
        assert payload["projection"]["evidence"]["as_of"] == as_of
        if ledger_state == "events":
            replay = run_status(tmp_path, as_of=None)["projection"]
            observed = datetime.fromisoformat(replay["evidence"]["observed_until"])
            expected_age = int((datetime.fromisoformat("2026-09-06T00:00:00+00:00") - observed).total_seconds() * 1000)
            assert payload["projection"]["stall"]["last_event_age_ms"] == expected_age
        else:
            assert payload["projection"]["integrity"]["status"] == "invalid"
    else:
        assert "as_of must be a timezone-aware ISO-8601 timestamp" in result.stderr
        assert not result.stdout
    assert (path.read_bytes() if path.exists() else None) == before
