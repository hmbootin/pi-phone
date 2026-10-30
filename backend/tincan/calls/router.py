"""Consumes ARI events and decides what each new call is."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tincan import store
from tincan.ari.events import AriConnected, AriDisconnected, AriEvent, StasisStart
from tincan.calls import policy
from tincan.calls.session import CallSession
from tincan.models import Contact, utcnow
from tincan.tts import prompts

if TYPE_CHECKING:
    from tincan.runtime import Runtime

log = logging.getLogger(__name__)

REJECTION_PROMPTS = {
    "busy": prompts.LINE_BUSY,
    "rejected_unknown": prompts.NOTHING_THERE,
    "rejected_dnd": prompts.NOT_ALLOWED,
    "rejected_quiet_hours": prompts.QUIET_HOURS,
    "rejected_cap": prompts.DAILY_CAP,
}
INBOUND_REJECTION_PROMPTS = {
    "busy": prompts.INBOUND_BUSY,
    "rejected_dnd": prompts.INBOUND_DND,
    "rejected_quiet_hours": prompts.INBOUND_QUIET_HOURS,
}


def contact_policy(c: Contact | None) -> policy.ContactPolicy | None:
    if c is None:
        return None
    return policy.ContactPolicy(
        enabled=bool(c.enabled),
        inbound_allowed=bool(c.inbound_allowed),
        dnd_until=c.dnd_until_dt,
        max_call_minutes=c.max_call_minutes,
    )


class CallRouter:
    def __init__(self, rt: Runtime):
        self.rt = rt
        self.sessions: list[CallSession] = []
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._consume(), name="ari-events")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        for s in list(self.sessions):
            if s.task:
                s.task.cancel()
                try:
                    await s.task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

    @property
    def active(self) -> CallSession | None:
        """The session that holds the line (not the ones just playing a rejection)."""
        for s in self.sessions:
            if s.outcome is None or s.outcome in ("time_cap",):
                return s
        return None

    def session_done(self, s: CallSession) -> None:
        if s in self.sessions:
            self.sessions.remove(s)

    async def wait_idle(self, timeout: float = 5.0) -> None:
        """Test helper: wait until no session is running."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        quiet = 0
        while loop.time() < deadline:
            await asyncio.sleep(0.005)
            pending = getattr(self.rt.ari, "_queue", None)
            busy = bool(self.sessions) or (pending is not None and not pending.empty())
            quiet = 0 if busy else quiet + 1
            if quiet >= 3:
                return
        raise TimeoutError(f"sessions still running: {self.sessions}")

    async def _consume(self) -> None:
        async for ev in self.rt.ari.events():
            try:
                self.dispatch(ev)
            except Exception:
                log.exception("error handling %s", type(ev).__name__)

    def dispatch(self, ev: AriEvent) -> None:
        if isinstance(ev, AriConnected | AriDisconnected):
            self.rt.ari_connected = isinstance(ev, AriConnected)
            self.rt.events.publish(
                "status.changed",
                {"asterisk": "connected" if self.rt.ari_connected else "disconnected"},
            )
            return
        if isinstance(ev, StasisStart) and ev.args and ev.args[0] in ("dial", "inbound"):
            self.on_new_call(ev)
            return
        for s in list(self.sessions):
            s.handle_event(ev)

    # -- new calls ------------------------------------------------------------------------------

    def on_new_call(self, ev: StasisStart) -> None:
        kind = ev.args[0]
        if kind == "dial":
            self.on_dial(ev, ev.args[1] if len(ev.args) > 1 else "")
        else:
            self.on_inbound(ev)

    def _spawn(self, s: CallSession, coro) -> None:
        self.sessions.append(s)
        s.start(coro)

    def on_dial(self, ev: StasisStart, dialed: str) -> None:
        rt = self.rt
        settings = rt.settings()
        now = utcnow()
        digit = int(dialed[0]) if dialed[:1].isdigit() else None
        line_busy = self.active is not None
        # A contact is reached by a digit (speed dial) or by a memory key (m1..m9, sos).
        contact = store.contact_by_dialed(rt.db, dialed)
        if contact is not None:
            calls_today = store.outbound_calls_today(rt.db, settings, now)
            rejection = policy.check_outbound(
                contact_policy(contact), settings, now, calls_today, line_busy
            )
            call = store.create_call(
                rt.db, "outbound", contact_id=contact.id, remote_number=contact.number
            )
            s = CallSession(rt, call.id, "outbound", contact=contact, phone_channel=ev.channel.id)
            if rejection:
                log.info("call %s to %s rejected: %s", call.id, contact.name, rejection)
                s.outcome = rejection
                self._spawn(
                    s,
                    s.run_rejected(
                        rejection, REJECTION_PROMPTS[rejection].format(name=contact.spoken_name)
                    ),
                )
            else:
                self._spawn(s, s.run_outbound())
            return

        feature_row = store.feature_by_digit(rt.db, digit) if digit is not None else None
        kind = feature_row.kind if feature_row and feature_row.enabled else "none"
        feature = rt.features.get(kind) if kind != "none" else None
        call = store.create_call(rt.db, "feature", feature_kind=kind)
        s = CallSession(rt, call.id, "feature", phone_channel=ev.channel.id)
        if line_busy:
            s.outcome = "busy"
            self._spawn(s, s.run_rejected("busy", prompts.LINE_BUSY))
        elif feature is None:
            s.outcome = "rejected_unknown"
            self._spawn(s, s.run_rejected("rejected_unknown", prompts.NOTHING_THERE))
        else:
            config = store.feature_config(feature_row) if feature_row else {}
            self._spawn(s, s.run_feature(feature, config))

    def on_inbound(self, ev: StasisStart) -> None:
        rt = self.rt
        settings = rt.settings()
        now = utcnow()
        number = ev.channel.caller_number
        contact = store.contact_by_number(rt.db, number)
        line_busy = self.active is not None
        rejection = policy.check_inbound(contact_policy(contact), settings, now, line_busy)
        call = store.create_call(
            rt.db, "inbound", contact_id=contact.id if contact else None, remote_number=number
        )
        s = CallSession(rt, call.id, "inbound", contact=contact, far_channel=ev.channel.id)
        if rejection:
            s.outcome = rejection
        if rejection == "rejected_unknown":
            log.info("inbound from %s rejected: unknown", number)
            self._spawn(
                s, s.run_unknown_caller(voicemail=settings.unknown_caller_policy == "voicemail")
            )
        elif rejection:
            log.info("inbound from %s rejected: %s", number, rejection)
            self._spawn(s, s.run_inbound_rejected(rejection, INBOUND_REJECTION_PROMPTS[rejection]))
        else:
            self._spawn(s, s.run_inbound())

    async def start_test_call(self, contact: Contact | None) -> int:
        if self.active is not None:
            raise RuntimeError("line busy")
        call = store.create_call(
            self.rt.db, "feature", contact_id=contact.id if contact else None, feature_kind="test"
        )
        s = CallSession(self.rt, call.id, "feature", contact=contact)
        self._spawn(s, s.run_test_call())
        return call.id

    async def hangup_active(self) -> bool:
        s = self.active
        if s is None:
            return False
        for cid in (s.phone_channel, s.far_channel):
            if cid and cid not in s.gone:
                await self.rt.ari.hangup(cid)
        return True
