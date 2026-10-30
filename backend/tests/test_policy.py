from datetime import UTC, datetime, timedelta

from tincan.calls import policy
from tincan.calls.policy import ContactPolicy
from tincan.schemas import QuietHours, Settings

CHI = QuietHours(start="19:30", end="07:30", tz="America/Chicago")


def chicago(h: int, m: int = 0) -> datetime:
    # 2026-06-15 is CDT (UTC-5); build the UTC instant for a local Chicago time.
    return datetime(2026, 6, 15, h, m, tzinfo=UTC) + timedelta(hours=5)


def test_quiet_hours_spanning_midnight():
    assert policy.in_quiet_hours(CHI, chicago(20))
    assert policy.in_quiet_hours(CHI, chicago(23, 59))
    assert policy.in_quiet_hours(CHI, chicago(3))
    assert policy.in_quiet_hours(CHI, chicago(7, 29))
    assert not policy.in_quiet_hours(CHI, chicago(7, 30))
    assert not policy.in_quiet_hours(CHI, chicago(12))
    assert not policy.in_quiet_hours(CHI, chicago(19, 29))
    assert policy.in_quiet_hours(CHI, chicago(19, 30))


def test_quiet_hours_same_day_and_disabled():
    nap = QuietHours(start="13:00", end="15:00", tz="America/Chicago")
    assert policy.in_quiet_hours(nap, chicago(14))
    assert not policy.in_quiet_hours(nap, chicago(16))
    assert not policy.in_quiet_hours(None, chicago(14))
    assert not policy.in_quiet_hours(QuietHours(start="08:00", end="08:00"), chicago(8))


def test_outbound_order_of_checks():
    s = Settings(daily_call_cap=2)
    now = chicago(12)
    ok = ContactPolicy()
    assert policy.check_outbound(ok, s, now, 0, line_busy=False) is None
    assert policy.check_outbound(ok, s, now, 0, line_busy=True) == "busy"
    assert policy.check_outbound(None, s, now, 0, line_busy=False) == "rejected_unknown"
    assert policy.check_outbound(ContactPolicy(enabled=False), s, now, 0, False) == "rejected_dnd"
    dnd = ContactPolicy(dnd_until=now + timedelta(hours=1))
    assert policy.check_outbound(dnd, s, now, 0, False) == "rejected_dnd"
    expired = ContactPolicy(dnd_until=now - timedelta(minutes=1))
    assert policy.check_outbound(expired, s, now, 0, False) is None
    assert policy.check_outbound(ok, s, chicago(21), 0, False) == "rejected_quiet_hours"
    assert policy.check_outbound(ok, s, now, 2, False) == "rejected_cap"
    assert policy.check_outbound(ok, s, now, 1, False) is None
    assert policy.check_outbound(ok, Settings(daily_call_cap=0), now, 99, False) is None


def test_inbound_checks():
    s = Settings()
    now = chicago(12)
    assert policy.check_inbound(None, s, now, False) == "rejected_unknown"
    assert (
        policy.check_inbound(ContactPolicy(inbound_allowed=False), s, now, False)
        == "rejected_unknown"
    )
    assert policy.check_inbound(ContactPolicy(enabled=False), s, now, False) == "rejected_unknown"
    assert (
        policy.check_inbound(ContactPolicy(dnd_until=now + timedelta(hours=1)), s, now, False)
        == "rejected_dnd"
    )
    assert policy.check_inbound(ContactPolicy(), s, chicago(22), False) == "rejected_quiet_hours"
    assert policy.check_inbound(ContactPolicy(), s, now, True) == "busy"
    assert policy.check_inbound(ContactPolicy(), s, now, False) is None


def test_time_cap_math():
    s = Settings(max_call_minutes=10, warning_seconds_before_end=60)
    assert policy.max_call_seconds(None, s) == 600
    assert policy.warning_at_seconds(None, s) == 540
    assert policy.max_call_seconds(ContactPolicy(max_call_minutes=3), s) == 180
    assert policy.warning_at_seconds(ContactPolicy(max_call_minutes=1), s) is None
    assert policy.warning_at_seconds(None, Settings(warning_seconds_before_end=0)) is None


def test_originate_endpoint():
    assert policy.originate_endpoint("+15555550123") == "PJSIP/+15555550123@trunk"
    assert policy.originate_endpoint("sip:grandma@example.org") == "PJSIP/sip:grandma@example.org"
