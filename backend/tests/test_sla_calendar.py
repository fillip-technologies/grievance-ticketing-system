"""Business-hours SLA due-date math — pure functions, no DB needed."""

from datetime import datetime, timezone

from app.services import sla_calendar


class _Settings:
    business_hours_enabled = True
    business_start_hour = 9
    business_end_hour = 18
    business_days = "1,2,3,4,5"  # Mon-Fri
    timezone = "UTC"
    holiday_dates = ""


def _dt(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def test_disabled_business_hours_is_plain_wall_clock():
    s = _Settings()
    s.business_hours_enabled = False
    start = _dt(2026, 8, 7, 18, 0)  # Friday 6pm
    assert sla_calendar.compute_due_at(start, 2, s) == _dt(2026, 8, 7, 20, 0)


def test_same_day_within_window():
    s = _Settings()
    start = _dt(2026, 8, 5, 10, 0)  # Wednesday 10am
    assert sla_calendar.compute_due_at(start, 2, s) == _dt(2026, 8, 5, 12, 0)


def test_spills_into_next_business_day():
    s = _Settings()
    start = _dt(2026, 8, 5, 17, 0)  # Wednesday 5pm — 1h left today
    # 1h today (to 6pm) + 3h tomorrow from 9am -> noon Thursday
    assert sla_calendar.compute_due_at(start, 4, s) == _dt(2026, 8, 6, 12, 0)


def test_friday_evening_skips_the_weekend():
    s = _Settings()
    start = _dt(2026, 8, 7, 18, 0)  # Friday 6pm (2026-08-07 is a Friday)
    assert sla_calendar.compute_due_at(start, 2, s) == _dt(2026, 8, 10, 11, 0)  # Monday 11am


def test_weekend_submission_lands_on_next_business_day():
    s = _Settings()
    start = _dt(2026, 8, 8, 3, 0)  # Saturday 3am
    assert sla_calendar.compute_due_at(start, 2, s) == _dt(2026, 8, 10, 11, 0)  # Monday 11am


def test_holiday_is_skipped_like_a_weekend():
    s = _Settings()
    s.holiday_dates = "2026-08-10"  # the Monday after the Friday below
    start = _dt(2026, 8, 7, 18, 0)  # Friday 6pm
    assert sla_calendar.compute_due_at(start, 2, s) == _dt(2026, 8, 11, 11, 0)  # Tuesday 11am


def test_invalid_calendar_falls_back_to_wall_clock():
    s = _Settings()
    s.business_days = ""  # no business days configured — can't compute a window
    start = _dt(2026, 8, 5, 10, 0)
    assert sla_calendar.compute_due_at(start, 2, s) == _dt(2026, 8, 5, 12, 0)


def test_parse_business_days_ignores_garbage():
    assert sla_calendar.parse_business_days("1, 2,x,9,5") == {1, 2, 5}


def test_parse_holidays_ignores_malformed_dates():
    from datetime import date
    assert sla_calendar.parse_holidays("2026-01-26, not-a-date, 2026-08-15") == {
        date(2026, 1, 26), date(2026, 8, 15),
    }
