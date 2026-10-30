"""The phone-side state machine: hook + keys + baresip events -> tones, dialing, ringing.

States:
  idle        handset down, nothing happening
  dial_tone   handset up, dial tone in the earpiece, waiting for a key
  dialing     a key was pressed; baresip has been told to dial and we wait for the call to connect
  ringing     incoming call; the base speaker rings until the handset lifts or the caller gives up
  in_call     audio flows through baresip; keys are sent as DTMF

Every transition that can fail (dial, answer) falls back to a friendly tone and dial tone, never
silence and never an open line (CLAUDE.md). The machine never dials on its own: on boot with the
handset already lifted it plays dial tone and waits for a key.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from enum import StrEnum
from typing import Any

from tincan.hardware.base import Audio, Inputs, Phone, PhoneEvent
from tincan.hardware.keys import HookEvent, InputEvent, KeyEvent, is_dialable, is_dtmf
from tincan.hardware.sounds import RING_OFF_SECONDS, RING_ON_SECONDS, SoundSet

log = logging.getLogger(__name__)


class PhoneState(StrEnum):
    IDLE = "idle"
    DIAL_TONE = "dial_tone"
    DIALING = "dialing"
    RINGING = "ringing"
    IN_CALL = "in_call"


Publisher = Callable[[str, dict[str, Any]], None]


class PhoneStateMachine:
    def __init__(
        self,
        inputs: Inputs,
        audio: Audio,
        phone: Phone,
        sounds: SoundSet,
        sip_host: str = "127.0.0.1",
        publish: Publisher | None = None,
        ringer_volume: Callable[[], int] | None = None,
        ringtone: Callable[[], SoundSet] | None = None,
    ):
        self.inputs = inputs
        self.audio = audio
        self.phone = phone
        self.sounds = sounds
        self.sip_host = sip_host
        self._publish = publish or (lambda event, data: None)
        self._ringer_volume = ringer_volume or (lambda: 80)
        self._sounds_now = ringtone or (lambda: self.sounds)
        self.state = PhoneState.IDLE
        self.off_hook = False
        self.dialed: str | None = None
        self.peer: str | None = None
        self._queue: asyncio.Queue[InputEvent | PhoneEvent] = asyncio.Queue()
        self._tasks: list[asyncio.Task[None]] = []
        self._lock = asyncio.Lock()
        self.history: list[PhoneState] = []

    # -- lifecycle ----------------------------------------------------------------------------

    async def start(self) -> None:
        self.off_hook = self.inputs.off_hook()
        self._tasks = [
            asyncio.create_task(self._pump(self.inputs.events()), name="phone-inputs"),
            asyncio.create_task(self._pump(self.phone.events()), name="phone-sip"),
            asyncio.create_task(self._run(), name="phone-machine"),
        ]
        if self.off_hook:
            log.warning("booted with the handset off-hook: dial tone, no auto-dial")
            await self._enter(PhoneState.DIAL_TONE)
        else:
            self._announce()

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._tasks = []
        await self._quiet()

    async def _pump(self, stream: AsyncIterator[Any]) -> None:
        async for ev in stream:
            self._queue.put_nowait(ev)

    async def _run(self) -> None:
        while True:
            ev = await self._queue.get()
            try:
                async with self._lock:
                    await self.handle(ev)
            except Exception:
                log.exception("phone machine failed on %s; going to a safe state", ev)
                await self._fail_safe()

    async def wait_idle(self, timeout: float = 2.0) -> None:
        """Test helper: wait until the event queue has drained."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            await asyncio.sleep(0.005)
            if self._queue.empty() and not self._lock.locked():
                return
        raise TimeoutError("phone machine still busy")

    # -- transitions --------------------------------------------------------------------------

    def _announce(self) -> None:
        self._publish(
            "phone.changed",
            {
                "state": self.state.value,
                "off_hook": self.off_hook,
                "dialed": self.dialed,
                "peer": self.peer,
                "sip": "connected" if self.phone.connected else "disconnected",
            },
        )

    async def _enter(self, state: PhoneState) -> None:
        if state is not self.state:
            log.info("phone: %s -> %s", self.state.value, state.value)
        self.state = state
        self.history.append(state)
        if state is PhoneState.DIAL_TONE:
            await self.audio.stop_ring()
            await self.audio.play_handset(self.sounds.dial_tone, loop=True)
        elif state is PhoneState.IDLE:
            self.dialed = self.peer = None
            await self._quiet()
        elif state is PhoneState.RINGING:
            s = self._sounds_now()
            await self.audio.ring(
                s.ringtone, RING_ON_SECONDS, RING_OFF_SECONDS, self._ringer_volume()
            )
        else:  # DIALING, IN_CALL: baresip owns the handset audio
            await self.audio.stop_ring()
            await self.audio.stop_handset()
        self._announce()

    async def _quiet(self) -> None:
        await self.audio.stop_ring()
        await self.audio.stop_handset()

    async def _tone_then_dial_tone(self, tone: Any) -> None:
        """Play a short tone into the handset, then go back to dial tone."""
        await self.audio.play_handset(tone, loop=False)
        await self._enter(PhoneState.DIAL_TONE)

    async def _fail_safe(self) -> None:
        try:
            await self.phone.hangup()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.off_hook:
                await self._tone_then_dial_tone(self.sounds.error)
            else:
                await self._enter(PhoneState.IDLE)
        except Exception:  # noqa: BLE001
            log.exception("could not even reach a safe state")

    # -- events -------------------------------------------------------------------------------

    async def handle(self, ev: InputEvent | PhoneEvent) -> None:
        if isinstance(ev, HookEvent):
            await self.on_hook(ev.off_hook)
        elif isinstance(ev, KeyEvent):
            if ev.pressed:
                await self.on_key(ev.key)
        elif isinstance(ev, PhoneEvent):
            await self.on_phone(ev)

    async def on_hook(self, off_hook: bool) -> None:
        if off_hook == self.off_hook:
            return
        self.off_hook = off_hook
        if off_hook:
            if self.state is PhoneState.RINGING:
                await self._answer()
            elif self.state is PhoneState.IDLE:
                await self._enter(PhoneState.DIAL_TONE)
            else:
                self._announce()
            return
        # handset went down: whatever was happening is over
        if self.state in (PhoneState.DIALING, PhoneState.IN_CALL):
            try:
                await self.phone.hangup()
            except Exception as exc:  # noqa: BLE001
                log.warning("hangup failed: %s", exc)
        await self._enter(PhoneState.IDLE)

    async def on_key(self, key: str) -> None:
        if self.state is PhoneState.DIAL_TONE and is_dialable(key):
            await self._dial(key)
        elif self.state is PhoneState.IN_CALL and is_dtmf(key):
            try:
                await self.phone.send_dtmf(key)
            except Exception as exc:  # noqa: BLE001
                log.warning("dtmf %s failed: %s", key, exc)
        else:
            log.debug("key %s ignored in %s", key, self.state.value)

    async def _dial(self, key: str) -> None:
        await self.audio.stop_handset()
        uri = f"sip:{key}@{self.sip_host}"
        if not self.phone.connected:
            log.error("cannot dial %s: sip client not connected", uri)
            await self._tone_then_dial_tone(self.sounds.error)
            return
        try:
            await self.phone.dial(uri)
        except Exception as exc:  # noqa: BLE001
            log.error("dial %s failed: %s", uri, exc)
            await self._tone_then_dial_tone(self.sounds.error)
            return
        self.dialed = key
        await self._enter(PhoneState.DIALING)

    async def _answer(self) -> None:
        await self.audio.stop_ring()
        try:
            await self.phone.answer()
        except Exception as exc:  # noqa: BLE001
            log.error("answer failed: %s", exc)
            await self._tone_then_dial_tone(self.sounds.error)
            return
        await self._enter(PhoneState.IN_CALL)

    async def on_phone(self, ev: PhoneEvent) -> None:
        if ev.kind == "incoming":
            self.peer = ev.peer
            if self.state is PhoneState.IDLE:
                await self._enter(PhoneState.RINGING)
            elif self.state is PhoneState.DIAL_TONE:
                # toddler already holding the handset: just connect them
                await self._answer()
            else:
                log.info("incoming call while %s; baresip will reject it", self.state.value)
        elif ev.kind == "established":
            if self.state in (PhoneState.DIALING, PhoneState.RINGING):
                if self.state is PhoneState.RINGING:
                    await self.audio.stop_ring()
                await self._enter(PhoneState.IN_CALL)
        elif ev.kind in ("closed", "disconnected"):
            if ev.kind == "disconnected":
                self._announce()
            if self.state is PhoneState.RINGING:
                await self._enter(PhoneState.IDLE)
            elif self.state in (PhoneState.DIALING, PhoneState.IN_CALL):
                self.dialed = self.peer = None
                if self.off_hook:
                    await self._tone_then_dial_tone(self.sounds.call_ended)
                else:
                    await self._enter(PhoneState.IDLE)
        elif ev.kind == "connected":
            self._announce()
