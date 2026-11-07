"""The student's timetable (F1, D1).

Entries are weekly and recurring (`weekday` + `start` + `end`); this module turns
them into the next concrete class relative to "now", where "now" is the demo clock
when Settings sends one (D2). Only the dates shift — the courses, times and rooms
come from the real timetable.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "timetable.json"
LOOKAHEAD_DAYS = 7

# How long after a class starts it is still the one you are trying to get to.
# A student five minutes late still wants directions to that room; half an hour in,
# what they need is the next class, not timings for one they are already sitting in.
LATE_GRACE_MIN = 20


def _load_entries() -> list[dict]:
    try:
        with DATA_FILE.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[timetable] could not read {DATA_FILE.name}: {exc}")
        return []
    entries = payload.get("entries", [])
    return [entry for entry in entries if isinstance(entry, dict)]


def _at(day: date, clock: str, tzinfo) -> datetime | None:
    try:
        hour, minute = (int(part) for part in clock.split(":")[:2])
    except (ValueError, AttributeError):
        return None
    return datetime.combine(day, time(hour, minute), tzinfo=tzinfo)


def _to_class_info(entry: dict, start: datetime, end: datetime) -> dict:
    title = f"{entry.get('course', 'Class')} ({entry.get('type', 'Class')})"
    return {
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "building_id": entry.get("building_id", ""),
        "room_id": entry.get("room_id", ""),
        "room_label": entry.get("room_label", entry.get("room_id", "")),
    }


def next_class(now: datetime) -> dict | None:
    """The class the student is trying to get to, as a ClassInfo dict.

    Upcoming classes, plus one that started within `LATE_GRACE_MIN` — so arriving
    late is still supported, but a class you are already well into is not reported
    as the one you are travelling to.
    """
    entries = _load_entries()
    if not entries:
        return None

    cutoff = now - timedelta(minutes=LATE_GRACE_MIN)
    candidates: list[tuple[datetime, dict]] = []
    for offset in range(LOOKAHEAD_DAYS + 1):
        day = now.date() + timedelta(days=offset)
        for entry in entries:
            if entry.get("weekday") != day.weekday():
                continue
            start = _at(day, entry.get("start", ""), now.tzinfo)
            end = _at(day, entry.get("end", ""), now.tzinfo)
            if start is None or end is None or start <= cutoff or end <= now:
                continue
            candidates.append((start, _to_class_info(entry, start, end)))

    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]


def week(now: datetime) -> list[dict]:
    """Every class in the next 7 days, earliest first — for the Calendar page."""
    entries = _load_entries()
    found: list[tuple[datetime, dict]] = []
    for offset in range(LOOKAHEAD_DAYS):
        day = now.date() + timedelta(days=offset)
        for entry in entries:
            if entry.get("weekday") != day.weekday():
                continue
            start = _at(day, entry.get("start", ""), now.tzinfo)
            end = _at(day, entry.get("end", ""), now.tzinfo)
            if start is None or end is None:
                continue
            found.append((start, _to_class_info(entry, start, end)))
    found.sort(key=lambda pair: pair[0])
    return [class_info for _, class_info in found]


def class_id(class_info: dict | None) -> str | None:
    """Stable id for "have we already reminded them about this class?"."""
    if not class_info:
        return None
    return f"{class_info.get('title', '')}@{class_info.get('start', '')}"


def minutes_until(class_info: dict | None, now: datetime) -> float | None:
    if not class_info or not class_info.get("start"):
        return None
    try:
        start = datetime.fromisoformat(class_info["start"])
    except ValueError:
        return None
    return (start - now).total_seconds() / 60


def human_when(class_info: dict | None, now: datetime) -> str:
    """"in 23 minutes", "at 14:00", "tomorrow at 09:00", "on Monday at 09:00".

    A countdown in minutes is only useful close to the class; "in 2563 minutes" is
    not something you would say out loud.
    """
    if not class_info or not class_info.get("start"):
        return ""
    try:
        start = datetime.fromisoformat(class_info["start"])
    except ValueError:
        return ""

    minutes = (start - now).total_seconds() / 60
    clock = start.strftime("%H:%M")

    if 0 <= minutes < 90:
        return f"in {round(minutes)} minutes" if minutes >= 1 else "right now"
    days = (start.date() - now.date()).days
    if days == 0:
        return f"at {clock}"
    if days == 1:
        return f"tomorrow at {clock}"
    return f"on {start:%A} at {clock}"


def local_time(iso: str | None) -> str:
    """"2026-11-07T09:00:00+00:00" -> "09:00", for spoken replies."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except ValueError:
        return ""
