async def test_all_ten_digits_with_speed_dial(client, grandma):
    r = await client.get("/api/features")
    feats = r.json()
    assert [f["digit"] for f in feats] == list(range(10))
    assert feats[2]["kind"] == "speed_dial"
    assert feats[2]["config"]["contact_id"] == grandma["id"]
    assert all(f["kind"] == "none" for f in feats if f["digit"] != 2)


async def test_put_and_preview(client, grandma):
    r = await client.put("/api/features/7", json={"kind": "fun_fact", "config": {"topic": "space"}})
    assert r.status_code == 200
    assert r.json() == {
        "digit": 7,
        "kind": "fun_fact",
        "config": {"topic": "space"},
        "enabled": True,
    }
    r = await client.put("/api/features/2", json={"kind": "weather"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "speed_dial_taken"
    r = await client.put("/api/features/7", json={"kind": "bogus"})
    assert r.status_code == 422

    r = await client.post("/api/features/7/preview")
    assert r.status_code == 200
    body = r.json()
    assert body["text"].startswith("Here's a fun fact about space.")
    assert body["audio_url"].startswith("/api/audio/prompts/")
    audio = await client.get(body["audio_url"])
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/wav"

    r = await client.post("/api/features/2/preview")
    assert r.json()["text"] == "Calling Grandma."


async def test_preview_secret_and_mailbox(client):
    await client.put(
        "/api/features/8", json={"kind": "secret_message", "config": {"recipient": "Dad"}}
    )
    r = await client.post("/api/features/8/preview")
    assert "Dad" in r.json()["text"]
    await client.put("/api/features/9", json={"kind": "mailbox"})
    r = await client.post("/api/features/9/preview")
    assert r.json()["text"] == "No new messages. Bye bye!"
