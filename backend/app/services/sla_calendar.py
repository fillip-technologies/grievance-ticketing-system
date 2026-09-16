"""Business-hours SLA due-date calculation.

When an org has `business_hours_enabled = False` (the default), SLA due dates are plain
wall-clock — `now + timedelta(hours=due_hours)` — identical to the platform's original
behavior. When enabled, `compute_due_at` only accumulates SLA hours during the org's
configured business days/window in its timezone, skipping non-business days and any
date listed in `holiday_dates`, so a complaint filed at 6pm Friday doesn't silently
breach over a weekend nobody was working.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("grievance_desk.sla_calendar")

_MAX_DAY_STEPS = 3660  # ~10 years of calendar days — guards against a misconfigured org
# (e.g. business_days empty) turning this into an infinite loop.


def parse_business_days(raw: str) -> set[int]:
    """Parses 'business_days' ("1,2,3,4,5") into a set of ISO weekdays (Mon=1..Sun=7)."""
    days: set[int] = set()
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            n = int(token)
        except ValueError:
            continue
        if 1 <= n <= 7:
            days.add(n)
    return days


def parse_holidays(raw: str) -> set[date]:
    """Parses 'holiday_dates' ("2026-01-26,2026-08-15") into a set of dates."""
    out: set[date] = set()
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            out.add(date.fromisoformat(token))
        except ValueError:
            continue
    return out


def _resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone %r on org settings — falling back to UTC.", name)
        return ZoneInfo("UTC")


def compute_due_at(start: datetime, hours: float, org_settings) -> datetime:
    """Returns the UTC datetime `hours` of *business time* after `start`, per the org's
    business-hours settings. Falls back to plain wall-clock if business hours are disabled
    or the configuration can't produce a valid business window (e.g. no business days set)."""
    if not getattr(org_settings, "business_hours_enabled", False):
        return start + timedelta(hours=hours)

    business_days = parse_business_days(org_settings.business_days)
    start_hour = org_settings.business_start_hour
    end_hour = org_settings.business_end_hour
    if not business_days or not (0 <= start_hour < end_hour <= 24):
        logger.warning(
            "Org has business_hours_enabled but an invalid calendar (days=%r, %s-%s) — "
            "falling back to wall-clock SLA for this ticket.", org_settings.business_days, start_hour, end_hour,
        )
        return start + timedelta(hours=hours)

    tz = _resolve_tz(org_settings.timezone)
    holidays = parse_holidays(org_settings.holiday_dates)
    cursor = start.astimezone(tz)
    remaining = timedelta(hours=hours)

    def is_business_day(d: datetime) -> bool:
        return d.isoweekday() in business_days and d.date() not in holidays

    def day_start(d: datetime) -> datetime:
        return d.replace(hour=start_hour, minute=0, second=0, microsecond=0)

    def day_end(d: datetime) -> datetime:
        return d.replace(hour=end_hour, minute=0, second=0, microsecond=0)

    def next_day_start(d: datetime) -> datetime:
        return day_start(d + timedelta(days=1))

    # Snap the cursor forward into the next valid business window.
    for _ in range(_MAX_DAY_STEPS):
        if not is_business_day(cursor):
            cursor = next_day_start(cursor)
            continue
        if cursor < day_start(cursor):
            cursor = day_start(cursor)
        elif cursor >= day_end(cursor):
            cursor = next_day_start(cursor)
            continue
        break
    else:
        return start + timedelta(hours=hours)  # unreachable in practice; safety fallback

    for _ in range(_MAX_DAY_STEPS):
        if remaining <= timedelta(0):
            break
        available_today = day_end(cursor) - cursor
        if remaining <= available_today:
            cursor = cursor + remaining
            remaining = timedelta(0)
        else:
            remaining -= available_today
            cursor = next_day_start(cursor)
            while not is_business_day(cursor):
                cursor = next_day_start(cursor)

    return cursor.astimezone(timezone.utc)
