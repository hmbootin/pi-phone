import asyncio

from tests.conftest import calls, settle
from tests.fake_ari import CAUSE_BUSY


async def test_speed_dial_bridges_records_and_logs(client, rt, ari, grandma):
    await client.patch("/api/settings", json={"trunk_caller_id": "+15555550100"})
    phone = ari.dial("2")
    # wait until the far leg is up and bridged
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.bridge_recordings():
            break
    assert ari.originated_endpoints() == ["PJSIP/+15555550123@trunk"]
    assert ari.originates[0]["caller_id"] == "+15555550100"
    assert len(ari.bridges) == 1
    bridged = next(iter(ari.bridges.values()))
    assert phone in bridged and len(bridged) == 2
    assert "Calling Grandma Jo." in rt.tts.rendered

    r = await client.get("/api/calls/active")
    assert r.json()["direction"] == "outbound" and r.json()["answered_at"]

    ari.hangup_channel(phone)  # toddler hangs up
    await settle(rt)

    (call,) = await calls(client)
    assert call["outcome"] == "completed"
    assert call["contact_id"] == grandma["id"]
    assert call["ended_at"] and call["duration_seconds"] is not None
    assert call["recording_id"]
    r = await client.get("/api/recordings")
    (rec,) = r.json()
    assert (
        rec["kind"] == "call"
        and rec["call_id"] == call["id"]
        and rec["contact_id"] == grandma["id"]
    )
    assert rec["size_bytes"] > 0 and rec["backed_up_at"] is None and rec["listened"] is False
    assert rt.events.history[-1][0] == "call.ended"
    assert any(e == "recording.created" for e, _ in rt.events.history)
    assert any(e == "call.started" for e, _ in rt.events.history)
    assert (await client.get("/api/calls/active")).json() is None


async def test_far_end_hangs_up(client, rt, ari, grandma):
    ari.dial("2")
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.bridge_recordings():
            break
    far = [c for c in ari.channels if c not in ari.phone_channels()][0]
    ari.hangup_channel(far)
    await settle(rt)
    (call,) = await calls(client)
    assert call["outcome"] == "completed"
    assert ari.hangups  # phone leg was hung up by us


async def test_time_cap_beeps_and_hangs_up(client, rt, ari, grandma):
    await client.patch(
        "/api/settings", json={"max_call_minutes": 1, "warning_seconds_before_end": 30}
    )
    ari.dial("2")
    await settle(rt, timeout=5)
    (call,) = await calls(client)
    assert call["outcome"] == "time_cap"
    media = ari.played_media()
    beeps = [m for m in media if m.endswith("/beep")]
    assert beeps and media.index(beeps[0]) < len(media) - 1  # beep then goodbye
    assert "Time's up! Bye bye!" in rt.tts.rendered
    assert len(ari.channels) == 0


async def test_busy_and_no_answer(client, rt, ari, grandma):
    ari.fail_next_originate = CAUSE_BUSY
    ari.dial("2")
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "busy"
    assert "Grandma Jo is busy right now. Let's try again later. Bye bye!" in rt.tts.rendered

    ari.auto_answer_delay = None  # nobody picks up; ring timeout (scaled) expires
    await client.patch("/api/settings", json={"ring_timeout_seconds": 5})
    ari.dial("2")
    await settle(rt, timeout=5)
    assert (await calls(client))[0]["outcome"] == "no_answer"
    assert not ari.bridges


async def test_toddler_gives_up_while_ringing(client, rt, ari, grandma):
    ari.auto_answer_delay = None
    phone = ari.dial("2")
    await asyncio.sleep(0.05)
    ari.hangup_channel(phone)
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "no_answer"
    assert len(ari.channels) == 0


async def test_policy_rejections_are_logged(client, rt, ari, grandma):
    cid = grandma["id"]
    await client.post(f"/api/contacts/{cid}/dnd", json={"minutes": 60})
    ari.dial("2")
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "rejected_dnd"
    assert not ari.originates
    await client.post(f"/api/contacts/{cid}/dnd", json={"clear": True})

    await client.patch(
        "/api/settings", json={"quiet_hours": {"start": "00:00", "end": "23:59", "tz": "UTC"}}
    )
    ari.dial("2")
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "rejected_quiet_hours"
    await client.patch("/api/settings", json={"quiet_hours": None, "daily_call_cap": 1})

    phone = ari.dial("2")
    await asyncio.sleep(0.1)
    ari.hangup_channel(phone)
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "completed"
    ari.dial("2")
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "rejected_cap"
    assert "That's a lot of calls today! Let's call again tomorrow. Bye bye!" in rt.tts.rendered

    ari.dial("5")  # nothing mapped
    await settle(rt)
    top = (await calls(client))[0]
    assert top["direction"] == "feature" and top["outcome"] == "rejected_unknown"


async def test_second_call_while_busy(client, rt, ari, grandma):
    await client.post(
        "/api/contacts", json={"name": "Mom", "number": "+15555550101", "speed_dial": 1}
    )
    ari.dial("2")
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.bridge_recordings():
            break
    ari.dial("1")
    await asyncio.sleep(0.05)
    r = await client.post("/api/calls/active/hangup")
    assert r.status_code == 204
    await settle(rt)
    outcomes = sorted(c["outcome"] for c in await calls(client))
    assert outcomes == ["busy", "completed"]


async def test_sip_contact_dials_direct(client, rt, ari):
    await client.post(
        "/api/contacts", json={"name": "Uncle", "number": "sip:uncle@example.org", "speed_dial": 3}
    )
    await client.patch(
        "/api/settings", json={"max_call_minutes": 1, "warning_seconds_before_end": 0}
    )
    ari.dial("3")
    await settle(rt, timeout=5)
    assert ari.originated_endpoints() == ["PJSIP/sip:uncle@example.org"]
    assert (await calls(client))[0]["outcome"] == "time_cap"
