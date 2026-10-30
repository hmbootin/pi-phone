import asyncio

from tests.conftest import calls, settle


async def wait_bridged(ari):
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.bridge_recordings():
            return
    raise AssertionError("never bridged")


async def test_known_caller_rings_phone_and_bridges(client, rt, ari, grandma):
    trunk = ari.inbound("5555550123")  # provider sends 10 digits; contact stored as E.164
    await wait_bridged(ari)
    assert ari.originated_endpoints() == ["PJSIP/phone"]
    assert ari.originates[0]["app_args"] == ["ring"]
    ari.hangup_channel(trunk)
    await settle(rt)
    (call,) = await calls(client)
    assert call["direction"] == "inbound" and call["outcome"] == "completed"
    assert call["contact_id"] == grandma["id"] and call["recording_id"]


async def test_unknown_caller_rejected(client, rt, ari, grandma):
    ari.inbound("+19998887777")
    await settle(rt)
    (call,) = await calls(client)
    assert call["outcome"] == "rejected_unknown" and call["contact_id"] is None
    assert not ari.originates
    assert "Sorry, this number can't take calls from you. Goodbye." in rt.tts.rendered


async def test_unknown_caller_voicemail(client, rt, ari, grandma):
    await client.patch("/api/settings", json={"unknown_caller_policy": "voicemail"})
    trunk = ari.inbound("+19998887777")
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.channel_recordings():
            break
    ari.hangup_channel(trunk)
    await settle(rt)
    (call,) = await calls(client)
    assert call["outcome"] == "rejected_unknown"
    r = await client.get("/api/recordings?kind=voicemail")
    (rec,) = r.json()
    assert rec["contact_id"] is None and rec["call_id"] == call["id"]
    assert rt.notifier.sent[-1]["title"] == "New voicemail"


async def test_quiet_hours_and_dnd_inbound(client, rt, ari, grandma):
    await client.patch(
        "/api/settings", json={"quiet_hours": {"start": "00:00", "end": "23:59", "tz": "UTC"}}
    )
    ari.inbound("+15555550123")
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "rejected_quiet_hours"
    assert rt.notifier.sent[-1]["title"] == "Call blocked"
    assert not ari.originates

    await client.patch("/api/settings", json={"quiet_hours": None})
    await client.post(f"/api/contacts/{grandma['id']}/dnd", json={"minutes": 30})
    ari.inbound("+15555550123")
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "rejected_dnd"

    await client.patch(
        f"/api/contacts/{grandma['id']}", json={"inbound_allowed": False, "dnd_until": None}
    )
    ari.inbound("+15555550123")
    await settle(rt)
    assert (await calls(client))[0]["outcome"] == "rejected_unknown"


async def test_no_answer_takes_voicemail_for_toddler(client, rt, ari, grandma):
    ari.auto_answer_delay = None
    await client.patch("/api/settings", json={"ring_timeout_seconds": 5})
    trunk = ari.inbound("+15555550123")
    for _ in range(200):
        await asyncio.sleep(0.01)
        if ari.channel_recordings():
            break
    assert ari.channel_recordings(), "caller should be offered voicemail after ring timeout"
    ari.hangup_channel(trunk)
    await settle(rt)
    (call,) = await calls(client)
    assert call["outcome"] == "no_answer"
    (rec,) = (await client.get("/api/recordings?kind=voicemail")).json()
    assert rec["contact_id"] == grandma["id"]
    assert rt.notifier.sent[-1]["title"] == "Missed call"


async def test_inbound_while_line_busy(client, rt, ari, grandma):
    ari.inbound("+15555550123")
    await wait_bridged(ari)
    second = ari.inbound("+15555550123")
    await asyncio.sleep(0.05)
    assert second not in ari.channels  # rejected and hung up
    await client.post("/api/calls/active/hangup")
    await settle(rt)
    assert sorted(c["outcome"] for c in await calls(client)) == ["busy", "completed"]
