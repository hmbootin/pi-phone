"""ORM rows. Timestamps are stored as ISO-8601 UTC text ("...Z")."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def dt_to_str(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def str_to_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Base(DeclarativeBase):
    pass


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    spoken_name: Mapped[str]
    number: Mapped[str]
    speed_dial: Mapped[int | None]
    enabled: Mapped[bool] = mapped_column(default=True)
    inbound_allowed: Mapped[bool] = mapped_column(default=True)
    dnd_until: Mapped[str | None] = mapped_column(String)
    max_call_minutes: Mapped[int | None]
    created_at: Mapped[str] = mapped_column(String, default=lambda: dt_to_str(utcnow()))

    @property
    def dnd_until_dt(self) -> datetime | None:
        return str_to_dt(self.dnd_until)


class Feature(Base):
    __tablename__ = "features"
    digit: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    config: Mapped[str] = mapped_column(default="{}")
    enabled: Mapped[bool] = mapped_column(default=True)


class SettingsRow(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[str]


class Call(Base):
    __tablename__ = "calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    direction: Mapped[str]
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    feature_kind: Mapped[str | None]
    remote_number: Mapped[str | None]
    started_at: Mapped[str] = mapped_column(String)
    answered_at: Mapped[str | None] = mapped_column(String)
    ended_at: Mapped[str | None] = mapped_column(String)
    duration_seconds: Mapped[int | None]
    outcome: Mapped[str | None]
    recording_id: Mapped[int | None]


class Recording(Base):
    __tablename__ = "recordings"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    call_id: Mapped[int | None] = mapped_column(ForeignKey("calls.id", ondelete="SET NULL"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    path: Mapped[str]
    created_at: Mapped[str] = mapped_column(String)
    duration_seconds: Mapped[int | None]
    size_bytes: Mapped[int | None]
    sha256: Mapped[str | None]
    backed_up_at: Mapped[str | None] = mapped_column(String)
    listened: Mapped[bool] = mapped_column(default=False)
