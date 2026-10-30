"""In-process fakes for the phone hardware, mirroring tincan.ari.fake for Asterisk.

`FakeInputs`/`FakeAudio`/`FakePhone` drive and observe the state machine in tests and in
`TINCAN_HARDWARE=fake` (the demo). When `FakePhone` is given the `FakeAri`, it closes the loop:
dialing `sip:2@...` makes a `PJSIP/phone` channel enter Stasis with `dial,2`; an ARI originate to
`PJSIP/phone` rings the fake phone; answering/hanging up on either side reaches the other.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tincan.hardware.base import PhoneEvent
from tincan.hardware.keys import HookEvent, InputEvent, KeyEvent

if TYPE_CHECKING:
    from tincan.ari.fake import FakeAri

log = logging.getLogger(__name__)


class _Stream:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._closed = False

    def push(self, ev: Any) -> None:
        self._queue.put_nowait(ev)

    async def events(self) -> AsyncIterator[Any]:
        while not self._closed:
            yield await self._queue.get()

    async def close(self) -> None:
        self._closed = True


class FakeInputs(_Stream):
    def __init__(self, off_hook: bool = False) -> None:
        super().__init__()
        self._off_hook = off_hook

    def off_hook(self) -> bool:
        return self._off_hook

    # -- driving -------------------------------------------------------------------------------

    def lift(self) -> None:
        self._off_hook = True
        self.push(HookEvent(off_hook=True))

    def hang_up(self) -> None:
        self._off_hook = False
        self.push(HookEvent(off_hook=False))

    def press(self, key: str) -> None:
        self.push(KeyEvent(key=key, pressed=True))
        self.push(KeyEvent(key=key, pressed=False))

    async def events(self) -> AsyncIterator[InputEvent]:  # type: ignore[override]
        async for ev in super().events():
            yield ev


class FakeAudio:
    def __init__(self) -> None:
        self.handset: Path | None = None
        self.handset_loop = False
        self.ringing: Path | None = None
        self.ring_volume: int | None = None
        self.played: list[str] = []  # "handset:<name>" / "ring:<name>" in order

    async def play_handset(self, path: Path, loop: bool = False) -> None:
        self.handset, self.handset_loop = path, loop
        self.played.append(f"handset:{path.stem}")

    async def stop_handset(self) -> None:
        self.handset = None

    async def ring(self, path: Path, on_seconds: float, off_seconds: float, volume: int) -> None:
        self.ringing, self.ring_volume = path, volume
        self.played.append(f"ring:{path.stem}")

    async def stop_ring(self) -> None:
        self.ringing = None

    async def close(self) -> None:
        pass


class FakePhone(_Stream):
    """A baresip stand-in. Optionally wired to the FakeAri so calls really traverse the router."""

    def __init__(self, ari: FakeAri | None = None, connected: bool = True) -> None:
        super().__init__()
        self._connected = connected
        self.ari = ari
        self.dials: list[str] = []
        self.dtmf: list[str] = []
        self.answers = 0
        self.hangups = 0
        self.fail_next_dial: Exception | None = None
        self.channel: str | None = None  # the PJSIP/phone channel id on the ARI side
        self.in_call = False
        if ari is not None:
            ari.phone = self

    @property
    def connected(self) -> bool:
        return self._connected

    def set_connected(self, value: bool) -> None:
        self._connected = value
        self.push(PhoneEvent("connected" if value else "disconnected"))

    # -- control -------------------------------------------------------------------------------

    async def dial(self, uri: str) -> None:
        if self.fail_next_dial is not None:
            exc, self.fail_next_dial = self.fail_next_dial, None
            raise exc
        self.dials.append(uri)
        if self.ari is None:
            return
        ext = uri.removeprefix("sip:").split("@", 1)[0]
        self.channel = self.ari.emit_stasis_start(["dial", ext])

    async def answer(self) -> None:
        self.answers += 1
        if self.ari is not None and self.channel is not None:
            self.ari.answer_originated(self.channel)
        self.in_call = True
        self.push(PhoneEvent("established", self.peer_for(self.channel)))

    async def hangup(self) -> None:
        self.hangups += 1
        self.in_call = False
        if self.ari is not None and self.channel is not None:
            cid, self.channel = self.channel, None
            self.ari.hangup_channel(cid)

    async def send_dtmf(self, digit: str) -> None:
        self.dtmf.append(digit)
        if self.ari is not None and self.channel is not None:
            self.ari.press_digit(self.channel, digit)

    def peer_for(self, channel: str | None) -> str | None:
        return channel

    # -- the far side (tests, or the FakeAri calling back) --------------------------------------

    def incoming(self, peer: str = "sip:asterisk", channel: str | None = None) -> None:
        self.channel = channel
        self.push(PhoneEvent("incoming", peer))

    def established(self) -> None:
        self.in_call = True
        self.push(PhoneEvent("established", self.channel))

    def closed(self, channel: str | None = None) -> None:
        """The far end hung up (or the ARI side destroyed our channel)."""
        if channel is not None and self.channel is not None and channel != self.channel:
            return
        self.channel = None
        self.in_call = False
        self.push(PhoneEvent("closed"))

    # -- FakeAri callbacks ---------------------------------------------------------------------

    def ari_originated(self, channel_id: str) -> None:
        """FakeAri.originate(endpoint="PJSIP/phone"): ring us instead of auto-answering."""
        self.incoming(peer="PJSIP/trunk", channel=channel_id)

    def ari_answered(self, channel_id: str) -> None:
        if channel_id == self.channel and not self.in_call:
            self.established()

    def ari_hung_up(self, channel_id: str) -> None:
        self.closed(channel_id)

    async def events(self) -> AsyncIterator[PhoneEvent]:  # type: ignore[override]
        async for ev in super().events():
            yield ev
