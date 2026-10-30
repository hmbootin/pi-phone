"""Pure policy decisions. No I/O, no clock: callers pass `now` (timezone-aware)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from tincan.schemas import QuietHours, Settings


@dataclass(frozen=True)
class ContactPolicy:
    """The slice of a contact that policy cares about."""

    enabled: bool = True
    inbound_allowed: bool = True
    dnd_until: datetime | None = None
    max_call_minutes: int | None = None


def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def in_quiet_hours(quiet: QuietHours | None, now: datetime) -> bool:
    """True when local time is inside [start, end). start > end means it spans midnight."""
    if quiet is None:
        return False
    local = now.astimezone(ZoneInfo(quiet.tz)).time().replace(second=0, microsecond=0)
    start, end = _hhmm(quiet.start), _hhmm(quiet.end)
    if start == end:
        return False
    if start < end:
        return start <= local < end
    return local >= start or local < end


def dnd_active(contact: ContactPolicy, now: datetime) -> bool:
    return contact.dnd_until is not None and contact.dnd_until > now


def check_outbound(
    contact: ContactPolicy | None,
    settings: Settings,
    now: datetime,
    calls_today: int,
    line_busy: bool,
) -> str | None:
    """Return a rejection outcome for a toddler-initiated call, or None if it may proceed."""
    if line_busy:
        return "busy"
    if contact is None:
        return "rejected_unknown"
    if not contact.enabled or dnd_active(contact, now):
        return "rejected_dnd"
    if in_quiet_hours(settings.quiet_hours, now):
        return "rejected_quiet_hours"
    if settings.daily_call_cap and calls_today >= settings.daily_call_cap:
        return "rejected_cap"
    return None


def check_inbound(
    contact: ContactPolicy | None,
    settings: Settings,
    now: datetime,
    line_busy: bool,
) -> str | None:
    """Return a rejection outcome for an incoming call, or None if the phone may ring."""
    if contact is None or not contact.enabled or not contact.inbound_allowed:
        return "rejected_unknown"
    if dnd_active(contact, now):
        return "rejected_dnd"
    if in_quiet_hours(settings.quiet_hours, now):
        return "rejected_quiet_hours"
    if line_busy:
        return "busy"
    return None


def max_call_seconds(contact: ContactPolicy | None, settings: Settings) -> int:
    minutes = settings.max_call_minutes
    if contact is not None and contact.max_call_minutes:
        minutes = contact.max_call_minutes
    return max(1, int(minutes)) * 60


def warning_at_seconds(contact: ContactPolicy | None, settings: Settings) -> int | None:
    """Seconds into the call when the warning beep plays, or None when there is no warning."""
    total = max_call_seconds(contact, settings)
    warn = settings.warning_seconds_before_end
    if warn <= 0 or warn >= total:
        return None
    return total - warn


def originate_endpoint(number: str, trunk: str = "trunk") -> str:
    """PJSIP dial string for a contact number: E.164 via the trunk, or a direct sip: URI."""
    if number.startswith("sip:"):
        return f"PJSIP/{number}"
    return f"PJSIP/{number}@{trunk}"
