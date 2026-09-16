"""Pure-function pieces of the ticket lifecycle — no DB needed."""

from datetime import timedelta

from app.services.ticket_service import _fmt_duration, priority_from_urgency


def test_priority_from_urgency_critical_always_wins():
    assert priority_from_urgency("Enquiry", "Critical") == "Critical"


def test_priority_from_urgency_high_urgency():
    assert priority_from_urgency("Enquiry", "High") == "High"


def test_priority_from_support_category_defaults_high():
    assert priority_from_urgency("Support", "Low") == "High"


def test_priority_from_enquiry_defaults_low():
    assert priority_from_urgency("Enquiry", "Low") == "Low"


def test_fmt_duration_hours_and_minutes():
    assert _fmt_duration(timedelta(hours=2, minutes=30)) == "2h 30m"


def test_fmt_duration_minutes_only():
    assert _fmt_duration(timedelta(minutes=45)) == "45m"


def test_fmt_duration_hours_only():
    assert _fmt_duration(timedelta(hours=1)) == "1h"


def test_fmt_duration_never_negative():
    assert _fmt_duration(timedelta(seconds=-500)) == "0m"
