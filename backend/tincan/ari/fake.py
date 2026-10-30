"""In-process fake of the ARI subset the backend uses.

Used by tests and by `TINCAN_FAKE_ARI=1` so the whole app runs without Asterisk. It records every
request (originates, bridges, recordings, playbacks) and offers helpers to drive the far end:
emit a StasisStart, answer an originated channel, hang up, fail an originate.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import struct
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tincan.ari.events import (
    AriConnected,
    AriEvent,
    Channel,
    ChannelDestroyed,
    ChannelDtmfReceived,
    ChannelStateChange,
    PlaybackFinished,
    RecordingFinished,
    StasisEnd,
    StasisStart,
)

log = logging.getLogger(__name__)

CAUSE_BUSY = 17
CAUSE_NO_ANSWER = 19
CAUSE_NORMAL = 16


@dataclass
class FakeChannel:
    id: str
    name: str
    state: str = "Ring"
    caller_number: str | None = None
    app_args: list[str] = field(default_factory=list)
    endpoint: str | None = None
    in_stasis: bool = False
    bridge_id: str | None = None
    recording: str | None = None

    def to_channel(self) -> Channel:
        return Channel(
            id=self.id, name=self.name, state=self.state, caller_number=self.caller_number
        )


@dataclass
class FakeRecording:
    name: str
    target: str  # "bridge:<id>" or "channel:<id>"
    finished: bool = False


class FakeAri:
    app = "tincan"

    def __init__(self, recordings_dir: Path | None = None, auto_answer_delay: float | None = 0.01):
        self.recordings_dir = recordings_dir
        self.auto_answer_delay = auto_answer_delay
        self.connected = True
        self.channels: dict[str, FakeChannel] = {}
        self.bridges: dict[str, list[str]] = {}
        self.recordings: dict[str, FakeRecording] = {}
        self.originates: list[dict[str, Any]] = []
        self.playbacks: list[dict[str, Any]] = []
        self.hangups: list[str] = []
        self.endpoints: dict[str, str] = {"PJSIP/phone": "online", "PJSIP/trunk": "online"}
        self.fail_next_originate: int | None = None
        self._queue: asyncio.Queue[AriEvent] = asyncio.Queue()
        self._seq = itertools.count(1)
        self._closed = False

    # -- event stream ---------------------------------------------------------------------------

    async def events(self) -> AsyncIterator[AriEvent]:
        yield AriConnected()
        while not self._closed:
            ev = await self._queue.get()
            yield ev

    async def close(self) -> None:
        self._closed = True

    def emit(self, ev: AriEvent) -> None:
        self._queue.put_nowait(ev)

    # -- helpers for tests and /api/dev/simulate ------------------------------------------------

    def new_channel_id(self, prefix: str = "PJSIP/phone") -> str:
        return f"{prefix}-{next(self._seq):08x}"

    def emit_stasis_start(
        self, args: list[str], caller: str | None = None, name_prefix: str = "PJSIP/phone"
    ) -> str:
        """A channel from the dialplan enters the Stasis app. Returns its id."""
        cid = self.new_channel_id(name_prefix)
        ch = FakeChannel(
            id=cid, name=cid, state="Ring", caller_number=caller, app_args=args, in_stasis=True
        )
        self.channels[cid] = ch
        self.emit(StasisStart(channel=ch.to_channel(), args=list(args)))
        return cid

    def phone_channels(self) -> list[str]:
        return [c.id for c in self.channels.values() if c.name.startswith("PJSIP/phone")]

    def answer_originated(self, channel_id: str) -> None:
        """Far end picks up: channel goes Up and enters Stasis with its appArgs."""
        ch = self.channels[channel_id]
        ch.state = "Up"
        ch.in_stasis = True
        self.emit(ChannelStateChange(channel=ch.to_channel()))
        self.emit(StasisStart(channel=ch.to_channel(), args=list(ch.app_args)))

    def hangup_channel(self, channel_id: str, cause: int = CAUSE_NORMAL) -> None:
        """Remote side hangs up (or an originate fails with `cause`)."""
        ch = self.channels.pop(channel_id, None)
        if ch is None:
            return
        if ch.bridge_id and ch.bridge_id in self.bridges:
            self.bridges[ch.bridge_id] = [c for c in self.bridges[ch.bridge_id] if c != channel_id]
        if ch.recording:
            self._finish_recording(ch.recording)
        if ch.in_stasis:
            self.emit(StasisEnd(channel=ch.to_channel()))
        self.emit(ChannelDestroyed(channel=ch.to_channel(), cause=cause, cause_txt=str(cause)))

    def press_digit(self, channel_id: str, digit: str) -> None:
        ch = self.channels[channel_id]
        self.emit(ChannelDtmfReceived(channel=ch.to_channel(), digit=digit))

    def _finish_recording(self, name: str) -> None:
        rec = self.recordings.get(name)
        if rec is None or rec.finished:
            return
        rec.finished = True
        duration = 1
        if self.recordings_dir is not None:
            path = self.recordings_dir / f"{name}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            write_silence_wav(path, seconds=0.1)
        self.emit(RecordingFinished(name=name, duration=duration))

    # -- control API (mirror of AriClient) ----------------------------------------------------

    async def answer(self, channel_id: str) -> None:
        ch = self.channels.get(channel_id)
        if ch and ch.state != "Up":
            ch.state = "Up"
            self.emit(ChannelStateChange(channel=ch.to_channel()))

    async def ring(self, channel_id: str) -> None:
        pass

    async def hangup(self, channel_id: str) -> None:
        self.hangups.append(channel_id)
        self.hangup_channel(channel_id, CAUSE_NORMAL)

    async def get_channel(self, channel_id: str) -> dict[str, Any] | None:
        ch = self.channels.get(channel_id)
        return {"id": ch.id, "name": ch.name, "state": ch.state} if ch else None

    async def originate(
        self,
        endpoint: str,
        app_args: str,
        channel_id: str,
        caller_id: str | None = None,
        timeout: int = 30,
    ) -> None:
        args = app_args.split(",") if app_args else []
        self.originates.append(
            {
                "endpoint": endpoint,
                "app_args": args,
                "channel_id": channel_id,
                "caller_id": caller_id,
            }
        )
        ch = FakeChannel(
            id=channel_id, name=channel_id, state="Ringing", app_args=args, endpoint=endpoint
        )
        self.channels[channel_id] = ch
        self.emit(ChannelStateChange(channel=ch.to_channel()))
        if self.fail_next_originate is not None:
            cause, self.fail_next_originate = self.fail_next_originate, None
            asyncio.get_running_loop().call_soon(self.hangup_channel, channel_id, cause)
            return
        if self.auto_answer_delay is not None:
            asyncio.get_running_loop().call_later(
                self.auto_answer_delay, self._auto_answer, channel_id
            )

    def _auto_answer(self, channel_id: str) -> None:
        if channel_id in self.channels and self.channels[channel_id].state != "Up":
            self.answer_originated(channel_id)

    async def play(self, channel_id: str, media: str, playback_id: str) -> None:
        self.playbacks.append(
            {"target": f"channel:{channel_id}", "media": media, "id": playback_id}
        )
        self.emit(PlaybackFinished(playback_id=playback_id, target_uri=f"channel:{channel_id}"))

    async def play_bridge(self, bridge_id: str, media: str, playback_id: str) -> None:
        self.playbacks.append({"target": f"bridge:{bridge_id}", "media": media, "id": playback_id})
        self.emit(PlaybackFinished(playback_id=playback_id, target_uri=f"bridge:{bridge_id}"))

    async def stop_playback(self, playback_id: str) -> None:
        pass

    async def create_bridge(self, bridge_id: str) -> None:
        self.bridges[bridge_id] = []

    async def add_to_bridge(self, bridge_id: str, *channel_ids: str) -> None:
        for cid in channel_ids:
            if cid in self.channels:
                self.bridges.setdefault(bridge_id, []).append(cid)
                self.channels[cid].bridge_id = bridge_id

    async def destroy_bridge(self, bridge_id: str) -> None:
        for cid in self.bridges.pop(bridge_id, []):
            if cid in self.channels:
                self.channels[cid].bridge_id = None
        for rec in self.recordings.values():
            if rec.target == f"bridge:{bridge_id}":
                self._finish_recording(rec.name)

    async def record_bridge(self, bridge_id: str, name: str, max_seconds: int = 0) -> None:
        self.recordings[name] = FakeRecording(name=name, target=f"bridge:{bridge_id}")

    async def record_channel(
        self,
        channel_id: str,
        name: str,
        max_seconds: int = 120,
        max_silence: int = 0,
        beep: bool = True,
    ) -> None:
        self.recordings[name] = FakeRecording(name=name, target=f"channel:{channel_id}")
        if channel_id in self.channels:
            self.channels[channel_id].recording = name

    async def stop_recording(self, name: str) -> None:
        self._finish_recording(name)

    async def get_endpoint(self, tech: str, resource: str) -> dict[str, Any] | None:
        key = f"{tech}/{resource}"
        if key not in self.endpoints:
            return None
        return {"technology": tech, "resource": resource, "state": self.endpoints[key]}

    # -- assertions ---------------------------------------------------------------------------

    def played_media(self) -> list[str]:
        return [p["media"] for p in self.playbacks]

    def bridge_recordings(self) -> list[str]:
        return [r.name for r in self.recordings.values() if r.target.startswith("bridge:")]

    def channel_recordings(self) -> list[str]:
        return [r.name for r in self.recordings.values() if r.target.startswith("channel:")]


def write_silence_wav(path: Path, seconds: float = 0.1, rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(rate * seconds))
