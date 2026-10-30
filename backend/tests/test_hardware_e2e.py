"""Fake keypad + fake baresip + fake Asterisk: a key press becomes a real routed call."""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import RecordingTts, calls, settle
from tests.fake_ari import TestAri
from tincan.config import Config
from tincan.hardware.machine import PhoneState


@pytest.fixture
def config(tmp_path):
    return Config(
        tincan_data_dir=tmp_path / "data",
        tincan_fake_ari=True,
        tincan_hardware="fake",
        tincan_time_scale=0.01,
        tincan_parent_password="parent-pw",
        tincan_secret_key="test-secret",
        piper_bin="definitely-not-installed-piper",
        _env_file=None,
    )


@pytest.fixture
async def app(config):
    from tincan import store
    from tincan.main import create_app
    from tincan.schemas import Settings

    application = create_app(config)
    rt = application.state.runtime
    # Same swap as conftest.app, plus re-pointing the fake baresip at the test flavour of the ARI.
    rt.fake = TestAri(recordings_dir=config.recordings_dir)
    rt.ari = rt.fake
    rt.phone.phone.ari = rt.fake
    rt.fake.phone = rt.phone.phone
    rt.tts = RecordingTts(config.prompts_dir, piper_bin=config.piper_bin)
    store.save_settings(rt.db, Settings(quiet_hours=None))
    await rt.start()
    await asyncio.sleep(0)
    yield application
    await rt.stop()


async def wait_state(machine, state: PhoneState, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if machine.state is state:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"phone is {machine.state}, wanted {state}")


async def test_press_m1_calls_grandma_and_hangup_ends_it(client, rt, ari, grandma):
    await client.patch(f"/api/contacts/{grandma['id']}", json={"memory_key": "m1"})
    m = rt.phone
    r = await client.post("/api/dev/simulate", json={"event": "offhook"})
    assert r.status_code == 200
    await wait_state(m, PhoneState.DIAL_TONE)
    await client.post("/api/dev/simulate", json={"event": "key", "key": "M1"})
    # the router answers the phone leg and bridges it to the trunk: baresip reports established
    await wait_state(m, PhoneState.IN_CALL)
    assert m.phone.dials == ["sip:m1@127.0.0.1"]
    assert m.history[-2:] == [PhoneState.DIALING, PhoneState.IN_CALL]
    # Grandma picks up (the fake trunk auto-answers) and the legs are bridged + recorded
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.bridge_recordings():
            break
    assert ari.originated_endpoints() == ["PJSIP/+15555550123@trunk"]
    assert ari.bridge_recordings()
    r = await client.get("/api/system/phone")
    assert r.json() == {
        "attached": True,
        "hardware": "fake",
        "state": "in_call",
        "off_hook": True,
        "dialed": "m1",
        "sip": "connected",
    }
    await client.post("/api/dev/simulate", json={"event": "onhook"})
    await wait_state(m, PhoneState.IDLE)
    await settle(rt)
    (call,) = await calls(client)
    assert call["outcome"] == "completed" and call["contact_id"] == grandma["id"]


async def test_unknown_key_prompt_then_dial_tone_again(client, rt, ari):
    m = rt.phone
    m.inputs.lift()
    await wait_state(m, PhoneState.DIAL_TONE)
    m.inputs.press("5")
    await settle(rt)  # the backend answers, speaks the prompt and hangs up
    await wait_state(m, PhoneState.DIAL_TONE)
    assert "Nothing is on that button. Try another one!" in rt.tts.rendered
    assert PhoneState.IN_CALL in m.history
    ended, tone = m.sounds.call_ended.stem, m.sounds.dial_tone.stem
    assert m.audio.played[-2:] == [f"handset:{ended}", f"handset:{tone}"]


async def test_inbound_rings_the_base_speaker_and_lifting_answers(client, rt, ari, grandma):
    m = rt.phone
    ari.inbound("+15555550123")
    await wait_state(m, PhoneState.RINGING)
    assert m.audio.ringing is not None
    m.inputs.lift()
    await wait_state(m, PhoneState.IN_CALL)
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.bridge_recordings():
            break
    assert ari.bridge_recordings()
    m.inputs.hang_up()
    await wait_state(m, PhoneState.IDLE)
    await settle(rt)
    (call,) = await calls(client)
    assert call["direction"] == "inbound" and call["outcome"] == "completed"


async def test_inbound_unanswered_stops_ringing(client, rt, ari, grandma):
    m = rt.phone
    ari.inbound("+15555550123")
    await wait_state(m, PhoneState.RINGING)
    await settle(rt, timeout=5)  # ring timeout (scaled) expires; voicemail prompt to the caller
    await wait_state(m, PhoneState.IDLE)
    assert m.audio.ringing is None
    (call,) = await calls(client)
    assert call["outcome"] == "no_answer"


async def test_status_without_hardware(client, rt):
    rt.phone = None
    r = await client.get("/api/system/phone")
    assert r.json() == {
        "attached": False,
        "hardware": "fake",
        "state": None,
        "off_hook": None,
        "dialed": None,
        "sip": None,
    }
