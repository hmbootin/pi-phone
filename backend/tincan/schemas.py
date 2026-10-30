"""Pydantic models for docs/api.md. Field names and outcome strings are the contract."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tincan import models

OUTCOMES = (
    "completed",
    "no_answer",
    "busy",
    "rejected_dnd",
    "rejected_quiet_hours",
    "rejected_unknown",
    "rejected_cap",
    "time_cap",
    "failed",
)
FEATURE_KINDS = ("speed_dial", "weather", "fun_fact", "secret_message", "mailbox", "song", "none")
RECORDING_KINDS = ("call", "secret", "voicemail")


class ContactIn(BaseModel):
    name: str = Field(min_length=1)
    spoken_name: str | None = None
    number: str = Field(min_length=1)
    speed_dial: int | None = Field(default=None, ge=0, le=9)
    enabled: bool = True
    inbound_allowed: bool = True
    dnd_until: datetime | None = None
    max_call_minutes: int | None = Field(default=None, ge=1)

    @field_validator("number")
    @classmethod
    def _number(cls, v: str) -> str:
        v = v.strip()
        if v.startswith("sip:"):
            return v
        digits = "".join(ch for ch in v if ch.isdigit())
        if not digits:
            raise ValueError("number must be E.164 or a sip: URI")
        return "+" + digits


class ContactPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    spoken_name: str | None = None
    number: str | None = None
    speed_dial: int | None = Field(default=None, ge=0, le=9)
    enabled: bool | None = None
    inbound_allowed: bool | None = None
    dnd_until: datetime | None = None
    max_call_minutes: int | None = None

    _number = field_validator("number")(ContactIn._number.__func__)  # type: ignore[attr-defined]


class ContactOut(BaseModel):
    id: int
    name: str
    spoken_name: str
    number: str
    speed_dial: int | None
    enabled: bool
    inbound_allowed: bool
    dnd_until: str | None
    max_call_minutes: int | None
    created_at: str

    @classmethod
    def from_row(cls, c: models.Contact) -> ContactOut:
        return cls(
            id=c.id,
            name=c.name,
            spoken_name=c.spoken_name,
            number=c.number,
            speed_dial=c.speed_dial,
            enabled=bool(c.enabled),
            inbound_allowed=bool(c.inbound_allowed),
            dnd_until=c.dnd_until,
            max_call_minutes=c.max_call_minutes,
            created_at=c.created_at,
        )


class DndIn(BaseModel):
    minutes: int | None = Field(default=None, ge=1)
    until: datetime | None = None
    clear: bool = False


class FeatureIn(BaseModel):
    kind: Literal["weather", "fun_fact", "secret_message", "mailbox", "song", "none"]
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class FeatureOut(BaseModel):
    digit: int
    kind: str
    config: dict[str, Any]
    enabled: bool

    @classmethod
    def from_row(cls, f: models.Feature) -> FeatureOut:
        return cls(
            digit=f.digit, kind=f.kind, config=json.loads(f.config or "{}"), enabled=bool(f.enabled)
        )


class PreviewOut(BaseModel):
    text: str
    audio_url: str


class QuietHours(BaseModel):
    start: str = "19:30"
    end: str = "07:30"
    tz: str = "America/Chicago"

    @field_validator("start", "end")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        h, m = v.split(":")
        if not (0 <= int(h) < 24 and 0 <= int(m) < 60):
            raise ValueError("expected HH:MM")
        return f"{int(h):02d}:{int(m):02d}"


class Notifications(BaseModel):
    ntfy_topic: str | None = None
    email: str | None = None


class WeatherLocation(BaseModel):
    lat: float = 30.27
    lon: float = -97.74
    name: str = "home"


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    max_call_minutes: int = Field(default=10, ge=1)
    warning_seconds_before_end: int = Field(default=60, ge=0)
    quiet_hours: QuietHours | None = Field(default_factory=QuietHours)
    daily_call_cap: int = Field(default=10, ge=0)
    ring_timeout_seconds: int = Field(default=25, ge=5)
    unknown_caller_policy: Literal["reject", "voicemail"] = "reject"
    notifications: Notifications = Field(default_factory=Notifications)
    trunk_caller_id: str | None = "+15555550100"
    weather_location: WeatherLocation = Field(default_factory=WeatherLocation)
    # A built-in name (classic, chime, birds) or an uploaded one; see tincan/sounds.
    ringtone: str = Field(default="classic", pattern=r"^[a-z0-9_-]{1,32}$")
    ringer_volume: int = Field(default=80, ge=0, le=100)


class RingtoneOut(BaseModel):
    name: str
    builtin: bool
    duration_seconds: float
    audio_url: str


class CallOut(BaseModel):
    id: int
    direction: str
    contact_id: int | None
    feature_kind: str | None
    started_at: str
    answered_at: str | None
    ended_at: str | None
    duration_seconds: int | None
    outcome: str | None
    recording_id: int | None

    @classmethod
    def from_row(cls, c: models.Call) -> CallOut:
        return cls(
            id=c.id,
            direction=c.direction,
            contact_id=c.contact_id,
            feature_kind=c.feature_kind,
            started_at=c.started_at,
            answered_at=c.answered_at,
            ended_at=c.ended_at,
            duration_seconds=c.duration_seconds,
            outcome=c.outcome,
            recording_id=c.recording_id,
        )


class RecordingOut(BaseModel):
    id: int
    kind: str
    call_id: int | None
    contact_id: int | None
    created_at: str
    duration_seconds: int | None
    size_bytes: int | None
    backed_up_at: str | None
    listened: bool
    audio_url: str

    @classmethod
    def from_row(cls, r: models.Recording) -> RecordingOut:
        return cls(
            id=r.id,
            kind=r.kind,
            call_id=r.call_id,
            contact_id=r.contact_id,
            created_at=r.created_at,
            duration_seconds=r.duration_seconds,
            size_bytes=r.size_bytes,
            backed_up_at=r.backed_up_at,
            listened=bool(r.listened),
            audio_url=f"/api/recordings/{r.id}/audio",
        )


class RecordingPatch(BaseModel):
    listened: bool | None = None


class BackupStatus(BaseModel):
    last_ok_at: str | None
    pending: int


class SystemStatus(BaseModel):
    asterisk: Literal["connected", "disconnected"]
    phone: Literal["registered", "unregistered"]
    trunk: Literal["registered", "unregistered", "unconfigured"]
    version: str
    disk_free_bytes: int
    backup: BackupStatus


class LoginIn(BaseModel):
    password: str


class TestCallIn(BaseModel):
    contact_id: int | None = None


class BackupReportIn(BaseModel):
    ids: list[int] = Field(default_factory=list)
    ok: bool = True
