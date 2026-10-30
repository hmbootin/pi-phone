import asyncio

from tests.conftest import calls, settle


async def test_fun_fact(client, rt, ari):
    await client.put("/api/features/7", json={"kind": "fun_fact", "config": {"topic": "dinosaurs"}})
    ari.dial("7")
    await settle(rt)
    (call,) = await calls(client)
    assert call["direction"] == "feature" and call["feature_kind"] == "fun_fact"
    assert call["outcome"] == "completed" and call["answered_at"]
    assert rt.tts.rendered[-1].startswith("Here's a fun fact about dinosaurs.")
    assert (rt.config.data_dir / "facts.json").exists()
    assert len(ari.channels) == 0


async def test_weather_uses_cache_and_fallback(client, rt, ari):
    await client.put("/api/features/6", json={"kind": "weather"})
    weather = rt.features["weather"]
    hits = []

    async def fake_fetch(lat, lon):
        hits.append((lat, lon))
        return {
            "current": {"temperature_2m": 71.6, "weather_code": 2},
            "daily": {"temperature_2m_max": [80.2]},
        }

    weather.fetch = fake_fetch
    ari.dial("6")
    await settle(rt)
    assert (
        rt.tts.rendered[-1]
        == "Right now in home it's 72 degrees and partly cloudy. Today's high is 80."
    )
    ari.dial("6")
    await settle(rt)
    assert len(hits) == 1  # cached

    async def broken(lat, lon):
        raise OSError("no network")

    weather.fetch = broken
    weather._cache.clear()
    ari.dial("6")
    await settle(rt)
    assert rt.tts.rendered[-1] == "I can't see the sky right now. Try again later!"
    assert (await calls(client))[0]["outcome"] == "completed"


async def test_secret_message_records_until_hangup(client, rt, ari):
    await client.put(
        "/api/features/8", json={"kind": "secret_message", "config": {"recipient": "Mom"}}
    )
    phone = ari.dial("8")
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ari.channel_recordings():
            break
    assert ari.channel_recordings() == [ari.channel_recordings()[0]]
    assert ari.channel_recordings()[0].split("/")[-1].startswith("secret-")
    ari.hangup_channel(phone)
    await settle(rt)
    (call,) = await calls(client)
    assert call["outcome"] == "completed"
    (rec,) = (await client.get("/api/recordings?kind=secret")).json()
    assert rec["call_id"] == call["id"]
    assert rt.notifier.sent[-1]["title"] == "New secret message"
    assert rt.events.history[-2][0] == "recording.created"


async def test_mailbox_plays_unlistened_voicemail(client, rt, ari, grandma):
    await client.put("/api/features/9", json={"kind": "mailbox"})
    ari.dial("9")
    await settle(rt)
    assert rt.tts.rendered[-1] == "No new messages. Bye bye!"

    # Grandma calls, nobody answers, she leaves a message.
    ari.auto_answer_delay = None
    await client.patch("/api/settings", json={"ring_timeout_seconds": 5})
    trunk = ari.inbound("+15555550123")
    for _ in range(200):
        await asyncio.sleep(0.01)
        if ari.channel_recordings():
            break
    ari.hangup_channel(trunk)
    await settle(rt)
    (vm,) = (await client.get("/api/recordings?kind=voicemail")).json()

    ari.auto_answer_delay = 0.01
    ari.dial("9")
    await settle(rt)
    said = rt.tts.rendered
    assert "You have 1 new messages." in said
    assert "Message from Grandma Jo." in said
    assert any(
        m.endswith(vm["audio_url"].split("/")[-2]) or "voicemail-" in m for m in ari.played_media()
    )
    (vm_after,) = (await client.get("/api/recordings?kind=voicemail")).json()
    assert vm_after["listened"] is True
    ari.dial("9")
    await settle(rt)
    assert rt.tts.rendered[-1] == "No new messages. Bye bye!"


async def test_unmapped_digit_is_safe(client, rt, ari):
    ari.dial("0")
    await settle(rt)
    assert rt.tts.rendered[-1] == "Nothing is on that button. Try another one!"
    assert len(ari.channels) == 0


async def test_feature_failure_falls_back_to_prompt(client, rt, ari):
    await client.put("/api/features/6", json={"kind": "weather"})

    async def boom(rt_, config):
        raise RuntimeError("kaboom")

    rt.features["weather"].text = boom  # type: ignore[method-assign]
    try:
        ari.dial("6")
        await settle(rt)
    finally:
        del rt.features["weather"].text
    assert (await calls(client))[0]["outcome"] == "failed"
    assert rt.tts.rendered[-1] == "Oops, that didn't work. Try again later."
    assert len(ari.channels) == 0


async def test_test_call_endpoint(client, rt, ari, grandma):
    r = await client.post("/api/system/test-call", json={"contact_id": grandma["id"]})
    assert r.status_code == 202
    await settle(rt)
    assert ari.originated_endpoints() == ["PJSIP/phone"]
    (call,) = await calls(client)
    assert call["feature_kind"] == "test" and call["outcome"] == "completed"
    assert rt.tts.rendered[-1] == "This is a test call from Tin Can. The line works. Bye bye!"


async def test_dev_simulate(client, rt, ari):
    await client.put("/api/features/7", json={"kind": "fun_fact"})
    r = await client.post("/api/dev/simulate", json={"event": "offhook_dial", "digit": "7"})
    assert r.status_code == 200
    await settle(rt)
    assert (await calls(client))[0]["feature_kind"] == "fun_fact"
    r = await client.post("/api/dev/simulate", json={"event": "nope"})
    assert r.status_code == 400
