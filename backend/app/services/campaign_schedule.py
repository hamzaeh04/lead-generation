"""Helpers for paced campaign sends inside a daily local time window."""
from __future__ import annotations

from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_ALLOWED_INTERVALS = {5, 10, 15, 30, 45, 60}


def parse_hhmm(value: str | None) -> time | None:
    if not value or not str(value).strip():
        return None
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time '{value}' — use HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time '{value}' — use HH:MM")
    return time(hour=hour, minute=minute)


def resolve_tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def is_within_window(now_utc: datetime, *, tz_name: str, start: str | None, end: str | None) -> bool:
    """True when no window is configured, or local time is inside [start, end)."""
    start_t = parse_hhmm(start)
    end_t = parse_hhmm(end)
    if start_t is None or end_t is None:
        return True
    local = now_utc.astimezone(resolve_tz(tz_name))
    local_t = local.timetz().replace(tzinfo=None)
    if start_t <= end_t:
        return start_t <= local_t < end_t
    # Overnight window (e.g. 22:00–06:00)
    return local_t >= start_t or local_t < end_t


def next_window_open(now_utc: datetime, *, tz_name: str, start: str | None, end: str | None) -> datetime:
    """Earliest UTC instant at/after now when sending is allowed."""
    start_t = parse_hhmm(start)
    end_t = parse_hhmm(end)
    if start_t is None or end_t is None:
        return now_utc
    if is_within_window(now_utc, tz_name=tz_name, start=start, end=end):
        return now_utc

    tz = resolve_tz(tz_name)
    local = now_utc.astimezone(tz)
    candidate = datetime.combine(local.date(), start_t, tzinfo=tz)
    if candidate <= local:
        candidate = candidate + timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def advance_send_slot(
    current_utc: datetime,
    *,
    tz_name: str,
    start: str | None,
    end: str | None,
    interval_minutes: int,
) -> datetime:
    """Move forward by interval minutes, skipping outside the daily window."""
    if interval_minutes not in _ALLOWED_INTERVALS:
        raise ValueError(f"Unsupported send interval: {interval_minutes}")
    nxt = current_utc + timedelta(minutes=interval_minutes)
    if is_within_window(nxt, tz_name=tz_name, start=start, end=end):
        return nxt
    return next_window_open(nxt, tz_name=tz_name, start=start, end=end)


def build_staggered_slots(
    count: int,
    *,
    now_utc: datetime,
    tz_name: str,
    start: str | None,
    end: str | None,
    interval_minutes: int,
) -> list[datetime]:
    if count <= 0:
        return []
    slot = next_window_open(now_utc, tz_name=tz_name, start=start, end=end)
    slots = [slot]
    for _ in range(1, count):
        slot = advance_send_slot(
            slot,
            tz_name=tz_name,
            start=start,
            end=end,
            interval_minutes=interval_minutes,
        )
        slots.append(slot)
    return slots
