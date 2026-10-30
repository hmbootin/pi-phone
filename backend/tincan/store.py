"""Small repository functions shared by the API and the call logic."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from tincan import models
from tincan.db import Database
from tincan.models import Call, Contact, Feature, Recording, SettingsRow, dt_to_str
from tincan.schemas import MEMORY_KEYS, Settings


def get_settings(db: Database) -> Settings:
    with db.session() as s:
        row = s.get(SettingsRow, 1)
        if row is None:
            return Settings()
        return Settings.model_validate(json.loads(row.data))


def save_settings(db: Database, settings: Settings) -> None:
    with db.session() as s:
        row = s.get(SettingsRow, 1)
        data = settings.model_dump_json()
        if row is None:
            s.add(SettingsRow(id=1, data=data))
        else:
            row.data = data


def contact_by_digit(db: Database, digit: int) -> Contact | None:
    with db.session() as s:
        return s.scalar(select(Contact).where(Contact.speed_dial == digit))


def contact_by_memory_key(db: Database, key: str) -> Contact | None:
    with db.session() as s:
        return s.scalar(select(Contact).where(Contact.memory_key == key))


def contact_by_dialed(db: Database, dialed: str) -> Contact | None:
    """What the phone dialed: a single digit ("2") or a memory key ("m1", "sos")."""
    if dialed[:1].isdigit():
        return contact_by_digit(db, int(dialed[0]))
    key = dialed.strip().lower()
    return contact_by_memory_key(db, key) if key in MEMORY_KEYS else None


def contact_by_id(db: Database, contact_id: int | None) -> Contact | None:
    if contact_id is None:
        return None
    with db.session() as s:
        return s.get(Contact, contact_id)


def normalize_number(number: str | None) -> str:
    if not number:
        return ""
    if number.startswith("sip:"):
        return number.lower()
    return "".join(ch for ch in number if ch.isdigit())


def contact_by_number(db: Database, number: str | None) -> Contact | None:
    """Match caller ID against contacts, tolerating missing country codes (last 10 digits)."""
    wanted = normalize_number(number)
    if not wanted:
        return None
    with db.session() as s:
        for c in s.scalars(select(Contact)):
            have = normalize_number(c.number)
            if not have:
                continue
            if have == wanted or (
                len(have) >= 10 and len(wanted) >= 10 and have[-10:] == wanted[-10:]
            ):
                return c
    return None


def feature_by_digit(db: Database, digit: int) -> Feature | None:
    with db.session() as s:
        return s.get(Feature, digit)


def feature_config(f: Feature) -> dict:
    return json.loads(f.config or "{}")


def outbound_calls_today(db: Database, settings: Settings, now: datetime) -> int:
    """Toddler-initiated calls today (local time) that were not rejected by policy."""
    tz = ZoneInfo(settings.quiet_hours.tz) if settings.quiet_hours else UTC
    local_midnight = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    since = dt_to_str(local_midnight.astimezone(UTC))
    with db.session() as s:
        return int(
            s.scalar(
                select(func.count())
                .select_from(Call)
                .where(Call.direction == "outbound")
                .where(Call.started_at >= since)
                .where((Call.outcome.is_(None)) | (Call.outcome.not_like("rejected_%")))
            )
            or 0
        )


def create_call(
    db: Database,
    direction: str,
    contact_id: int | None = None,
    feature_kind: str | None = None,
    remote_number: str | None = None,
) -> Call:
    with db.session() as s:
        call = Call(
            direction=direction,
            contact_id=contact_id,
            feature_kind=feature_kind,
            remote_number=remote_number,
            started_at=dt_to_str(models.utcnow()),
        )
        s.add(call)
        s.flush()
        return call


def update_call(db: Database, call_id: int, **fields) -> Call | None:
    with db.session() as s:
        call = s.get(Call, call_id)
        if call is None:
            return None
        for k, v in fields.items():
            setattr(call, k, v)
        return call


def finish_call(db: Database, call_id: int, outcome: str) -> Call | None:
    now = models.utcnow()
    with db.session() as s:
        call = s.get(Call, call_id)
        if call is None:
            return None
        if call.outcome is None:
            call.outcome = outcome
        call.ended_at = dt_to_str(now)
        answered = models.str_to_dt(call.answered_at)
        if answered is not None:
            call.duration_seconds = max(0, int((now - answered).total_seconds()))
        return call


def active_call(db: Database) -> Call | None:
    with db.session() as s:
        return s.scalar(select(Call).where(Call.ended_at.is_(None)).order_by(Call.id.desc()))


def create_recording(
    db: Database,
    kind: str,
    path: str,
    call_id: int | None,
    contact_id: int | None,
    duration_seconds: int | None,
    size_bytes: int | None,
    sha256: str | None,
) -> Recording:
    with db.session() as s:
        rec = Recording(
            kind=kind,
            call_id=call_id,
            contact_id=contact_id,
            path=path,
            created_at=dt_to_str(models.utcnow()),
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            sha256=sha256,
        )
        s.add(rec)
        s.flush()
        if call_id is not None and kind == "call":
            call = s.get(Call, call_id)
            if call is not None:
                call.recording_id = rec.id
        return rec


def unlistened_for_toddler(db: Database) -> list[Recording]:
    """Mailbox contents: voicemails from known contacts the toddler hasn't heard."""
    with db.session() as s:
        return list(
            s.scalars(
                select(Recording)
                .where(Recording.kind == "voicemail")
                .where(Recording.contact_id.is_not(None))
                .where(Recording.listened.is_(False))
                .order_by(Recording.id)
            )
        )


def mark_listened(db: Database, recording_id: int) -> None:
    with db.session() as s:
        rec = s.get(Recording, recording_id)
        if rec is not None:
            rec.listened = True


def dnd_active(contact: Contact, now: datetime) -> bool:
    until = contact.dnd_until_dt
    return until is not None and until > now


def dnd_for(minutes: int, now: datetime) -> str:
    return dt_to_str(now + timedelta(minutes=minutes)) or ""
