"""The phone-side state machine against the fakes, with no Asterisk in the loop."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tincan.hardware.fake import FakeAudio, FakeInputs, FakePhone
from tincan.hardware.keys import HookEvent, KeyEvent
from tincan.hardware.machine import PhoneState, PhoneStateMachine
from tincan.hardware.sounds import SoundSet

S = SoundSet(
    dial_tone=Path("/x/dial_tone.wav"),
    call_ended=Path("/x/call_ended.wav"),
    error=Path("/x/error.wav"),
    ringtone=Path("/x/ring_classic.wav"),
)


class Rig:
    def __init__(self, off_hook: bool = False, connected: bool = True):
        self.inputs = FakeInputs(off_hook=off_hook)
        self.audio = FakeAudio()
        self.phone = FakePhone(connected=connected)
        self.events: list[dict] = []
        self.machine = PhoneStateMachine(
            self.inputs,
            self.audio,
            self.phone,
            S,
            sip_host="asterisk",
            publish=lambda name, data: self.events.append({"event": name, **data}),
            ringer_volume=lambda: 55,
        )

    async def settle(self) -> PhoneState:
        await asyncio.sleep(0.01)
        await self.machine.wait_idle()
        await asyncio.sleep(0.01)
        return self.machine.state


@pytest.fixture
async def rig():
    r = Rig()
    await r.machine.start()
    yield r
    await r.machine.stop()


async def test_lift_gives_dial_tone_and_keys_dial(rig: Rig):
    assert rig.machine.state is PhoneState.IDLE
    rig.inputs.lift()
    assert await rig.settle() is PhoneState.DIAL_TONE
    assert rig.audio.handset == S.dial_tone and rig.audio.handset_loop

    rig.inputs.press("m1")
    assert await rig.settle() is PhoneState.DIALING
    assert rig.phone.dials == ["sip:m1@asterisk"]
    assert rig.audio.handset is None  # baresip owns the earpiece now
    assert rig.machine.dialed == "m1"

    rig.phone.established()
    assert await rig.settle() is PhoneState.IN_CALL
    rig.inputs.press("5")
    rig.inputs.press("flash")  # not DTMF: ignored
    await rig.settle()
    assert rig.phone.dtmf == ["5"]

    rig.inputs.hang_up()
    assert await rig.settle() is PhoneState.IDLE
    assert rig.phone.hangups == 1
    assert [e["state"] for e in rig.events] == ["idle", "dial_tone", "dialing", "in_call", "idle"]


async def test_keys_on_hook_do_nothing(rig: Rig):
    rig.inputs.press("2")
    rig.inputs.press("sos")
    assert await rig.settle() is PhoneState.IDLE
    assert rig.phone.dials == [] and rig.audio.played == []


async def test_only_dialable_keys_dial(rig: Rig):
    rig.inputs.lift()
    await rig.settle()
    for key in ("*", "#", "store", "speaker", "redial", "flash"):
        rig.inputs.press(key)
    assert await rig.settle() is PhoneState.DIAL_TONE
    assert rig.phone.dials == []
    rig.inputs.press("7")
    assert await rig.settle() is PhoneState.DIALING


async def test_far_end_hangs_up_while_handset_lifted(rig: Rig):
    rig.inputs.lift()
    rig.inputs.press("2")
    await rig.settle()
    rig.phone.established()
    await rig.settle()
    rig.phone.closed()
    assert await rig.settle() is PhoneState.DIAL_TONE
    # a friendly "call ended" tone first, then dial tone again, never silence
    assert rig.audio.played[-2:] == ["handset:call_ended", "handset:dial_tone"]
    rig.inputs.press("3")
    assert await rig.settle() is PhoneState.DIALING
    assert rig.phone.dials == ["sip:2@asterisk", "sip:3@asterisk"]


async def test_dial_failure_falls_back_to_dial_tone(rig: Rig):
    rig.inputs.lift()
    await rig.settle()
    rig.phone.fail_next_dial = RuntimeError("baresip said no")
    rig.inputs.press("2")
    assert await rig.settle() is PhoneState.DIAL_TONE
    assert rig.audio.played[-2:] == ["handset:error", "handset:dial_tone"]


async def test_dial_with_sip_disconnected(rig: Rig):
    rig.phone.set_connected(False)
    rig.inputs.lift()
    await rig.settle()
    rig.inputs.press("2")
    assert await rig.settle() is PhoneState.DIAL_TONE
    assert rig.phone.dials == []
    assert "handset:error" in rig.audio.played
    assert rig.events[-1]["sip"] == "disconnected"


async def test_incoming_call_rings_until_answered(rig: Rig):
    rig.phone.incoming(peer="PJSIP/trunk")
    assert await rig.settle() is PhoneState.RINGING
    assert rig.audio.ringing == S.ringtone and rig.audio.ring_volume == 55
    rig.inputs.press("2")  # mashing keys while it rings does nothing
    await rig.settle()
    assert rig.phone.dials == []
    rig.inputs.lift()
    assert await rig.settle() is PhoneState.IN_CALL
    assert rig.audio.ringing is None and rig.phone.answers == 1
    rig.inputs.hang_up()
    assert await rig.settle() is PhoneState.IDLE


async def test_caller_gives_up_stops_ringing(rig: Rig):
    rig.phone.incoming()
    await rig.settle()
    rig.phone.closed()
    assert await rig.settle() is PhoneState.IDLE
    assert rig.audio.ringing is None


async def test_incoming_while_holding_handset_is_answered(rig: Rig):
    rig.inputs.lift()
    await rig.settle()
    rig.phone.incoming()
    assert await rig.settle() is PhoneState.IN_CALL
    assert rig.phone.answers == 1 and rig.audio.ringing is None


async def test_boot_off_hook_does_not_dial():
    r = Rig(off_hook=True)
    await r.machine.start()
    try:
        assert await r.settle() is PhoneState.DIAL_TONE
        assert r.phone.dials == []
        r.inputs.hang_up()
        assert await r.settle() is PhoneState.IDLE
    finally:
        await r.machine.stop()


async def test_handler_exception_reaches_safe_state(rig: Rig, monkeypatch):
    rig.inputs.lift()
    await rig.settle()

    async def boom(uri: str) -> None:
        raise ValueError("unexpected")

    # simulate a bug deeper than the per-call try/except: break the audio layer instead
    async def broken_stop_handset() -> None:
        raise OSError("aplay vanished")

    monkeypatch.setattr(rig.audio, "stop_handset", broken_stop_handset)
    rig.inputs.press("2")
    await rig.settle()
    monkeypatch.undo()
    # the machine survived and the next event is still handled
    rig.inputs.hang_up()
    assert await rig.settle() is PhoneState.IDLE
    assert rig.machine._tasks and not any(t.done() for t in rig.machine._tasks)


async def test_release_and_duplicate_hook_events_are_ignored(rig: Rig):
    rig.inputs.push(HookEvent(off_hook=False))
    rig.inputs.push(KeyEvent("2", pressed=False))
    assert await rig.settle() is PhoneState.IDLE
    assert rig.audio.played == []
