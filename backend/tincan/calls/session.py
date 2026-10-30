"""One call, from StasisStart to the written call row.

A session owns at most two channels: `phone` (the baresip leg) and `far` (trunk or feature-less).
Flows are plain async functions that await ARI completion events through `wait_for`; a hangup
on any channel in `self.ends_call` raises `CallEnded` out of whatever the flow was waiting on,
and `run()` turns that into the right outcome and cleanup.

Timers (ring timeout, warning beep, hard cap) are asyncio timeouts scaled by
`TINCAN_TIME_SCALE` so tests can run them in milliseconds.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tincan import store
from tincan.ari.events import (
    AriEvent,
    ChannelDestroyed,
    ChannelDtmfReceived,
    PlaybackFinished,
    RecordingFailed,
    RecordingFinished,
    StasisEnd,
    StasisStart,
)
from tincan.calls import policy
from tincan.models import Contact, dt_to_str, utcnow
from tincan.tts import prompts
from tincan.tts.piper import BEEP, wav_duration_seconds

if TYPE_CHECKING:
    from tincan.runtime import Runtime

log = logging.getLogger(__name__)

CAUSE_BUSY = 17
CAUSE_NO_ANSWER = (18, 19)


class CallEnded(Exception):
    """A channel whose loss ends the call has hung up."""


class _Waiter:
    def __init__(self, pred: Callable[[AriEvent], bool]):
        self.pred = pred
        self.future: asyncio.Future[AriEvent] = asyncio.get_running_loop().create_future()


class CallSession:
    def __init__(
        self,
        rt: Runtime,
        call_id: int,
        direction: str,
        contact: Contact | None = None,
        phone_channel: str | None = None,
        far_channel: str | None = None,
    ):
        self.rt = rt
        self.ari = rt.ari
        self.call_id = call_id
        self.direction = direction
        self.contact = contact
        self.phone_channel = phone_channel
        self.far_channel = far_channel
        self.bridge_id: str | None = None
        self.recording_name: str | None = None
        self.ends_call: set[str] = set()
        self.gone: set[str] = set()
        self.ended = asyncio.Event()
        self.digits: list[str] = []
        self.outcome: str | None = None
        self.answered_at: datetime | None = None
        self.recording_id: int | None = None
        self.started = utcnow()
        self._waiters: list[_Waiter] = []
        self.task: asyncio.Task[None] | None = None
        self.settings = rt.settings()

    # -- events -------------------------------------------------------------------------------

    def handle_event(self, ev: AriEvent) -> None:
        if isinstance(ev, StasisEnd | ChannelDestroyed):
            cid = ev.channel.id
            self.gone.add(cid)
            if cid in self.ends_call:
                self.ended.set()
        if isinstance(ev, ChannelDtmfReceived) and ev.channel.id == self.phone_channel:
            self.digits.append(ev.digit)
        for w in list(self._waiters):
            if not w.future.done() and w.pred(ev):
                w.future.set_result(ev)

    def register(self, pred: Callable[[AriEvent], bool]) -> _Waiter:
        w = _Waiter(pred)
        self._waiters.append(w)
        return w

    def scaled(self, seconds: float) -> float:
        return seconds * self.rt.config.tincan_time_scale

    async def wait(
        self, waiter: _Waiter, timeout: float | None, ignore_hangup: bool = False
    ) -> AriEvent:
        """Wait for a registered event. Raises CallEnded on hangup, TimeoutError on timeout."""
        try:
            if ignore_hangup:
                return await asyncio.wait_for(
                    waiter.future, self.scaled(timeout) if timeout else None
                )
            if self.ended.is_set():
                raise CallEnded()
            gone = asyncio.ensure_future(self.ended.wait())
            try:
                done, _ = await asyncio.wait(
                    {waiter.future, gone},
                    timeout=self.scaled(timeout) if timeout else None,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                gone.cancel()
            if waiter.future in done:
                return waiter.future.result()
            if gone in done:
                raise CallEnded()
            raise TimeoutError()
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)

    async def wait_for(
        self, pred: Callable[[AriEvent], bool], timeout: float | None, ignore_hangup: bool = False
    ) -> AriEvent:
        return await self.wait(self.register(pred), timeout, ignore_hangup)

    async def sleep_unless_hangup(self, seconds: float) -> None:
        """Sleep; raise CallEnded if a call-ending channel hangs up first."""
        if self.ended.is_set():
            raise CallEnded()
        try:
            await asyncio.wait_for(self.ended.wait(), self.scaled(seconds))
        except TimeoutError:
            return
        raise CallEnded()

    # -- media helpers ------------------------------------------------------------------------

    async def play(self, media: str, channel: str | None = None, timeout: float = 120) -> None:
        cid = channel or self.phone_channel
        if cid is None or cid in self.gone:
            return
        pid = uuid.uuid4().hex
        w = self.register(lambda e: isinstance(e, PlaybackFinished) and e.playback_id == pid)
        await self.ari.play(cid, media, pid)
        try:
            await self.wait(w, timeout)
        except TimeoutError:
            await self.ari.stop_playback(pid)

    async def play_bridge(self, media: str, timeout: float = 30) -> None:
        if self.bridge_id is None:
            return
        pid = uuid.uuid4().hex
        w = self.register(lambda e: isinstance(e, PlaybackFinished) and e.playback_id == pid)
        await self.ari.play_bridge(self.bridge_id, media, pid)
        try:
            await self.wait(w, timeout)
        except TimeoutError:
            await self.ari.stop_playback(pid)

    async def say(self, text: str, channel: str | None = None) -> None:
        path = await self.rt.tts.render(text)
        await self.play(self.rt.tts.media_uri(path), channel)

    async def say_bridge(self, text: str) -> None:
        path = await self.rt.tts.render(text)
        await self.play_bridge(self.rt.tts.media_uri(path))

    async def beep(self, channel: str | None = None) -> None:
        await self.play(f"sound:{BEEP.with_suffix('')}", channel)

    def spoken_name(self) -> str:
        return self.contact.spoken_name if self.contact else "them"

    # -- lifecycle ----------------------------------------------------------------------------

    def start(self, coro: Any) -> None:
        self.task = asyncio.create_task(self._run(coro), name=f"call-{self.call_id}")

    async def _run(self, coro: Any) -> None:
        try:
            await coro
        except CallEnded:
            if self.outcome is None:
                self.outcome = "completed" if self.answered_at else "no_answer"
        except asyncio.CancelledError:
            self.outcome = self.outcome or "failed"
            raise
        except Exception:
            log.exception("call %s failed", self.call_id)
            self.outcome = self.outcome or "failed"
            await self._safe(self.say, prompts.FEATURE_FAILED)
        finally:
            await self.cleanup()

    async def _safe(self, fn: Callable[..., Any], *args: Any) -> None:
        try:
            await fn(*args)
        except CallEnded:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning("ignored during cleanup: %s", exc)

    async def cleanup(self) -> None:
        if self.recording_name is not None:
            await self._safe(self.finish_recording)
        if self.bridge_id is not None:
            await self._safe(self.ari.destroy_bridge, self.bridge_id)
            self.bridge_id = None
        for cid in (self.phone_channel, self.far_channel):
            if cid and cid not in self.gone:
                await self._safe(self.ari.hangup, cid)
        outcome = self.outcome or "failed"
        call = store.finish_call(self.rt.db, self.call_id, outcome)
        if call is not None:
            from tincan.schemas import CallOut

            self.rt.events.publish("call.ended", CallOut.from_row(call).model_dump())
        self.rt.router.session_done(self)

    def mark_answered(self) -> None:
        self.answered_at = utcnow()
        store.update_call(self.rt.db, self.call_id, answered_at=dt_to_str(self.answered_at))

    # -- recording ----------------------------------------------------------------------------

    def recording_base(self, prefix: str) -> str:
        now = datetime.now(UTC)
        return f"{now:%Y}/{now:%m}/{prefix}-{self.call_id}"

    async def start_bridge_recording(self) -> None:
        assert self.bridge_id
        name = self.recording_base("call")
        # Pre-create the directory on the shared mount so Asterisk can open the file.
        (self.rt.config.recordings_dir / name).parent.mkdir(parents=True, exist_ok=True)
        await self.ari.record_bridge(self.bridge_id, name)
        self.recording_name = name
        self._recording_kind = "call"

    async def start_channel_recording(
        self, channel: str, prefix: str, kind: str, max_seconds: int = 120
    ) -> None:
        name = self.recording_base(prefix)
        (self.rt.config.recordings_dir / name).parent.mkdir(parents=True, exist_ok=True)
        await self.ari.record_channel(
            channel, name, max_seconds=max_seconds, max_silence=0, beep=False
        )
        self.recording_name = name
        self._recording_kind = kind

    async def finish_recording(self, timeout: float = 5) -> int | None:
        """Stop the live recording, wait for Asterisk to close it, and write the recordings row."""
        name = self.recording_name
        if name is None:
            return None
        self.recording_name = None
        w = self.register(
            lambda e: isinstance(e, RecordingFinished | RecordingFailed) and e.name == name
        )
        await self.ari.stop_recording(name)
        duration: int | None = None
        try:
            ev = await self.wait(w, timeout, ignore_hangup=True)
            if isinstance(ev, RecordingFailed):
                log.warning("recording %s failed: %s", name, ev.cause)
            else:
                duration = ev.duration
        except TimeoutError:
            log.warning("no RecordingFinished for %s; indexing whatever is on disk", name)
        rel = f"{name}.wav"
        path = self.rt.config.recordings_dir / rel
        size = sha = None
        if path.exists():
            size = path.stat().st_size
            sha = await asyncio.to_thread(_sha256, path)
            duration = duration if duration is not None else wav_duration_seconds(path)
        elif duration is None:
            log.warning("recording file missing: %s", path)
            return None
        rec = store.create_recording(
            self.rt.db,
            kind=getattr(self, "_recording_kind", "call"),
            path=rel,
            call_id=self.call_id,
            contact_id=self.contact.id if self.contact else None,
            duration_seconds=duration,
            size_bytes=size,
            sha256=sha,
        )
        self.recording_id = rec.id
        from tincan.schemas import RecordingOut

        self.rt.events.publish("recording.created", RecordingOut.from_row(rec).model_dump())
        return rec.id

    # -- flows --------------------------------------------------------------------------------

    async def run_rejected(self, outcome: str, text: str) -> None:
        """Play the reason to the phone, hang up, record the attempt."""
        self.outcome = outcome
        if self.phone_channel:
            self.ends_call.add(self.phone_channel)
            await self.ari.answer(self.phone_channel)
            await self.say(text)

    async def run_outbound(self) -> None:
        """Toddler dialed a contact: ring them through the trunk, bridge, record, cap."""
        assert self.phone_channel and self.contact
        self.ends_call.add(self.phone_channel)
        await self.ari.answer(self.phone_channel)
        await self.say(prompts.CALLING.format(name=self.spoken_name()))

        far = uuid.uuid4().hex
        self.far_channel = far
        up = self.register(lambda e: isinstance(e, StasisStart) and e.channel.id == far)
        dead = self.register(lambda e: isinstance(e, ChannelDestroyed) and e.channel.id == far)
        ring = self.settings.ring_timeout_seconds
        await self.ari.originate(
            endpoint=policy.originate_endpoint(self.contact.number),
            app_args="far",
            channel_id=far,
            caller_id=self.settings.trunk_caller_id,
            timeout=ring,
        )
        try:
            ev = await self._first(up, dead, timeout=ring + 5)
        except TimeoutError:
            self.outcome = "no_answer"
            await self._safe(self.ari.hangup, far)
            await self.say(prompts.NO_ANSWER.format(name=self.spoken_name()))
            return
        if isinstance(ev, ChannelDestroyed):
            if ev.cause == CAUSE_BUSY:
                self.outcome = "busy"
                await self.say(prompts.BUSY.format(name=self.spoken_name()))
            elif ev.cause in CAUSE_NO_ANSWER:
                self.outcome = "no_answer"
                await self.say(prompts.NO_ANSWER.format(name=self.spoken_name()))
            else:
                self.outcome = "failed"
                await self.say(prompts.CALL_FAILED)
            return
        await self.bridged_phase()

    async def run_inbound(self) -> None:
        """A contact is calling: ring the phone, bridge on answer, record, cap."""
        assert self.far_channel and self.contact
        trunk = self.far_channel
        self.ends_call.add(trunk)
        await self.ari.ring(trunk)

        phone = uuid.uuid4().hex
        self.phone_channel = phone
        up = self.register(lambda e: isinstance(e, StasisStart) and e.channel.id == phone)
        dead = self.register(lambda e: isinstance(e, ChannelDestroyed) and e.channel.id == phone)
        ring = self.settings.ring_timeout_seconds
        await self.ari.originate(
            endpoint="PJSIP/phone", app_args="ring", channel_id=phone, timeout=ring
        )
        try:
            ev = await self._first(up, dead, timeout=ring + 5)
            answered = isinstance(ev, StasisStart)
        except TimeoutError:
            answered = False
        if not answered:
            self.outcome = "no_answer"
            await self._safe(self.ari.hangup, phone)
            self.phone_channel = None
            await self.ari.answer(trunk)
            await self.say(prompts.INBOUND_NO_ANSWER, channel=trunk)
            await self.record_until_hangup(trunk, prefix="voicemail", kind="voicemail")
            await self.rt.notify(
                "Missed call",
                f"{self.contact.name} called and nobody answered."
                + (" They left a message." if self.recording_id else ""),
            )
            return
        await self.ari.answer(trunk)
        await self.bridged_phase()

    async def run_feature(self, feature: Any, config: dict[str, Any]) -> None:
        assert self.phone_channel
        self.ends_call.add(self.phone_channel)
        await self.ari.answer(self.phone_channel)
        self.mark_answered()
        await feature.run(self, config)
        self.outcome = self.outcome or "completed"

    async def run_test_call(self) -> None:
        """Ring the phone and speak a test prompt when answered (POST /api/system/test-call)."""
        phone = uuid.uuid4().hex
        self.phone_channel = phone
        up = self.register(lambda e: isinstance(e, StasisStart) and e.channel.id == phone)
        dead = self.register(lambda e: isinstance(e, ChannelDestroyed) and e.channel.id == phone)
        ring = self.settings.ring_timeout_seconds
        await self.ari.originate(
            endpoint="PJSIP/phone", app_args="test", channel_id=phone, timeout=ring
        )
        try:
            ev = await self._first(up, dead, timeout=ring + 5)
        except TimeoutError:
            ev = None
        if not isinstance(ev, StasisStart):
            self.outcome = "no_answer"
            return
        self.ends_call.add(phone)
        self.mark_answered()
        await self.say(prompts.TEST_CALL)
        self.outcome = "completed"

    async def run_unknown_caller(self, voicemail: bool) -> None:
        assert self.far_channel
        trunk = self.far_channel
        self.ends_call.add(trunk)
        self.outcome = "rejected_unknown"
        await self.ari.answer(trunk)
        if not voicemail:
            await self.say(prompts.INBOUND_UNKNOWN, channel=trunk)
            return
        await self.say(prompts.INBOUND_UNKNOWN_VOICEMAIL, channel=trunk)
        await self.record_until_hangup(trunk, prefix="voicemail", kind="voicemail")
        if self.recording_id:
            await self.rt.notify("New voicemail", "An unknown caller left a message.")

    async def run_inbound_rejected(self, outcome: str, text: str) -> None:
        assert self.far_channel
        self.ends_call.add(self.far_channel)
        self.outcome = outcome
        await self.ari.answer(self.far_channel)
        await self.say(text, channel=self.far_channel)
        if self.contact is not None and outcome != "busy":
            why = "quiet hours" if outcome == "rejected_quiet_hours" else "do not disturb"
            await self.rt.notify("Call blocked", f"{self.contact.name} called during {why}.")

    async def record_until_hangup(
        self, channel: str, prefix: str, kind: str, max_seconds: int = 120
    ) -> None:
        """Record one channel until it hangs up (or max_seconds), then index the file."""
        await self.beep(channel)
        await self.start_channel_recording(channel, prefix, kind, max_seconds=max_seconds)
        name = self.recording_name
        done = self.register(
            lambda e: isinstance(e, RecordingFinished | RecordingFailed) and e.name == name
        )
        try:
            await self.wait(done, timeout=max_seconds + 5)
        except CallEnded:
            pass
        except TimeoutError:
            pass
        await self.finish_recording()

    async def bridged_phase(self) -> None:
        """Both legs are up: bridge, record, enforce the time cap, then clean up."""
        assert self.phone_channel and self.far_channel
        self.ends_call.update({self.phone_channel, self.far_channel})
        if self.ended.is_set():
            raise CallEnded()
        self.mark_answered()
        bridge = uuid.uuid4().hex
        await self.ari.create_bridge(bridge)
        self.bridge_id = bridge
        await self.ari.add_to_bridge(bridge, self.phone_channel, self.far_channel)
        await self.start_bridge_recording()
        self.rt.events.publish("call.started", self.rt.call_json(self.call_id))

        cp = policy.ContactPolicy(
            max_call_minutes=self.contact.max_call_minutes if self.contact else None
        )
        total = policy.max_call_seconds(cp, self.settings)
        warn_at = policy.warning_at_seconds(cp, self.settings)
        elapsed = 0
        if warn_at is not None:
            await self.sleep_unless_hangup(warn_at)
            elapsed = warn_at
            await self.play_bridge(f"sound:{BEEP.with_suffix('')}")
        await self.sleep_unless_hangup(max(0, total - elapsed))
        self.outcome = "time_cap"
        await self.say_bridge(prompts.GOODBYE)

    async def _first(self, *waiters: _Waiter, timeout: float) -> AriEvent:
        """Wait for whichever waiter fires first."""
        futs = [w.future for w in waiters]
        gone = asyncio.ensure_future(self.ended.wait())
        try:
            done, _ = await asyncio.wait(
                set(futs) | {gone},
                timeout=self.scaled(timeout),
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            gone.cancel()
            for w in waiters:
                if w in self._waiters:
                    self._waiters.remove(w)
        for f in futs:
            if f in done:
                return f.result()
        if gone in done:
            raise CallEnded()
        raise TimeoutError()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
