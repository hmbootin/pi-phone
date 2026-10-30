"""Typed ARI events. Only the fields the call logic uses are kept."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Channel:
    id: str
    name: str = ""
    state: str = ""
    caller_number: str | None = None
    caller_name: str | None = None
    dialplan_exten: str | None = None

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Channel:
        caller = d.get("caller") or {}
        dialplan = d.get("dialplan") or {}
        return cls(
            id=d["id"],
            name=d.get("name", ""),
            state=d.get("state", ""),
            caller_number=caller.get("number") or None,
            caller_name=caller.get("name") or None,
            dialplan_exten=dialplan.get("exten"),
        )


@dataclass
class AriEvent:
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class AriConnected(AriEvent):
    pass


@dataclass
class AriDisconnected(AriEvent):
    pass


@dataclass
class StasisStart(AriEvent):
    channel: Channel = field(default_factory=lambda: Channel(id=""))
    args: list[str] = field(default_factory=list)


@dataclass
class StasisEnd(AriEvent):
    channel: Channel = field(default_factory=lambda: Channel(id=""))


@dataclass
class ChannelDtmfReceived(AriEvent):
    channel: Channel = field(default_factory=lambda: Channel(id=""))
    digit: str = ""


@dataclass
class ChannelStateChange(AriEvent):
    channel: Channel = field(default_factory=lambda: Channel(id=""))


@dataclass
class ChannelDestroyed(AriEvent):
    channel: Channel = field(default_factory=lambda: Channel(id=""))
    cause: int = 0
    cause_txt: str = ""


@dataclass
class PlaybackFinished(AriEvent):
    playback_id: str = ""
    target_uri: str = ""


@dataclass
class RecordingFinished(AriEvent):
    name: str = ""
    duration: int | None = None
    format: str = "wav"


@dataclass
class RecordingFailed(AriEvent):
    name: str = ""
    cause: str = ""


@dataclass
class UnknownEvent(AriEvent):
    type: str = ""


def parse_event(d: dict[str, Any]) -> AriEvent:
    t = d.get("type", "")
    ch = d.get("channel")
    if t == "StasisStart":
        return StasisStart(raw=d, channel=Channel.from_json(ch), args=list(d.get("args") or []))
    if t == "StasisEnd":
        return StasisEnd(raw=d, channel=Channel.from_json(ch))
    if t == "ChannelDtmfReceived":
        return ChannelDtmfReceived(raw=d, channel=Channel.from_json(ch), digit=d.get("digit", ""))
    if t == "ChannelStateChange":
        return ChannelStateChange(raw=d, channel=Channel.from_json(ch))
    if t == "ChannelDestroyed":
        return ChannelDestroyed(
            raw=d,
            channel=Channel.from_json(ch),
            cause=int(d.get("cause", 0)),
            cause_txt=d.get("cause_txt", ""),
        )
    if t == "PlaybackFinished":
        pb = d.get("playback") or {}
        return PlaybackFinished(
            raw=d, playback_id=pb.get("id", ""), target_uri=pb.get("target_uri", "")
        )
    if t == "RecordingFinished":
        rec = d.get("recording") or {}
        return RecordingFinished(
            raw=d,
            name=rec.get("name", ""),
            duration=rec.get("duration"),
            format=rec.get("format", "wav"),
        )
    if t == "RecordingFailed":
        rec = d.get("recording") or {}
        return RecordingFailed(raw=d, name=rec.get("name", ""), cause=rec.get("cause", ""))
    return UnknownEvent(raw=d, type=t)
