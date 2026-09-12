"""Bounded calendar evaluation for the built-in periodic report subscription.

The profile format can describe schedules for other hosts. This evaluator
deliberately accepts only daily/weekly wall-clock schedules supported locally.
It calculates boundaries; it neither runs an Automation nor authorizes delivery.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .profile import _normalize_schedule

_DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def normalize_report_cadence(raw: object) -> dict[str, str] | None:
    schedule = _normalize_schedule(raw)
    if schedule is None:
        return None
    try:
        ZoneInfo(schedule["timezone"])
    except ZoneInfoNotFoundError as exc:
        raise ValueError("schedule.timezone is unknown") from exc
    fields: dict[str, str] = {}
    for item in schedule["rrule"].split(";"):
        key, separator, value = item.partition("=")
        if not separator or key in fields or not value:
            raise ValueError("schedule.rrule contains an empty or duplicate field")
        fields[key] = value
    if fields.get("FREQ") not in {"DAILY", "WEEKLY"}:
        raise ValueError("local report cadence supports FREQ=DAILY or WEEKLY")
    allowed = {"FREQ", "BYHOUR", "BYMINUTE", "INTERVAL"}
    if fields["FREQ"] == "WEEKLY":
        allowed.add("BYDAY")
        if fields.get("BYDAY") not in _DAYS:
            raise ValueError("weekly report cadence requires one BYDAY, MO through SU")
    if set(fields) - allowed or fields.get("INTERVAL", "1") != "1":
        raise ValueError("local report cadence supports one daily or weekly occurrence")
    for key, maximum in (("BYHOUR", 23), ("BYMINUTE", 59)):
        value = fields.get(key, "0" if key == "BYMINUTE" else "")
        if not value.isascii() or not value.isdigit() or not 0 <= int(value) <= maximum:
            raise ValueError(f"schedule.rrule {key} must be an integer from 0 to {maximum}")
        fields[key] = str(int(value))
    canonical = [f"FREQ={fields['FREQ']}"]
    if fields["FREQ"] == "WEEKLY":
        canonical.append(f"BYDAY={fields['BYDAY']}")
    canonical.extend(f"{key}={fields[key]}" for key in ("BYHOUR", "BYMINUTE"))
    return {**schedule, "rrule": ";".join(canonical)}


def report_cadence_window(raw: object, *, now: datetime) -> dict[str, Any] | None:
    """Return the latest completed interval and next boundary in UTC.

    Spring-forward nonexistent wall times are skipped; a fall-back occurrence
    uses its first fold only. These semantics match one report per local date.
    No cursor is advanced here; successful publication owns that state.
    """
    schedule = normalize_report_cadence(raw)
    if schedule is None:
        return None
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("cadence evaluation time must include a UTC offset")
    zone = ZoneInfo(schedule["timezone"])
    fields = dict(item.split("=", 1) for item in schedule["rrule"].split(";"))
    current = now.astimezone(timezone.utc)
    local_date = current.astimezone(zone).date()
    occurrences: list[datetime] = []
    # Two previous valid weekly boundaries even across a skipped DST date,
    # and the next valid boundary. Fixed bounds avoid unbounded RRULE work.
    for offset in range(-28, 15):
        day = local_date + timedelta(days=offset)
        if fields["FREQ"] == "WEEKLY" and day.weekday() != _DAYS.index(fields["BYDAY"]):
            continue
        wall = datetime.combine(day, time(int(fields["BYHOUR"]), int(fields["BYMINUTE"])))
        candidate = wall.replace(tzinfo=zone, fold=0).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) != wall:
            continue
        occurrences.append(candidate)
    past = [value for value in occurrences if value <= current]
    future = [value for value in occurrences if value > current]
    if len(past) < 2 or not future:
        raise ValueError("schedule has no supported bounded calendar window")
    def stamp(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
    return {
        "schedule": schedule,
        "start_at": stamp(past[-2]),
        "due_at": stamp(past[-1]),
        "next_due_at": stamp(future[0]),
    }
