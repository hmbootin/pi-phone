from tests.conftest import calls, settle


async def make_call(client, rt, ari):
    await client.patch(
        "/api/settings", json={"max_call_minutes": 1, "warning_seconds_before_end": 0}
    )
    ari.dial("2")
    await settle(rt, timeout=5)
    (call,) = await calls(client)
    assert call["recording_id"]
    return call


async def test_audio_range_patch_and_backup(client, rt, ari, grandma):
    await client.patch(
        "/api/settings", json={"max_call_minutes": 1, "warning_seconds_before_end": 0}
    )
    call = await make_call(client, rt, ari)
    rid = call["recording_id"]
    r = await client.get("/api/recordings")
    (rec,) = r.json()
    assert rec["id"] == rid and rec["audio_url"] == f"/api/recordings/{rid}/audio"
    assert set(rec) == {
        "id", "kind", "call_id", "contact_id", "created_at", "duration_seconds", "size_bytes",
        "backed_up_at", "listened", "audio_url",
    }  # fmt: skip

    full = await client.get(rec["audio_url"])
    assert full.status_code == 200 and full.headers["content-type"] == "audio/wav"
    assert full.content[:4] == b"RIFF" and len(full.content) == rec["size_bytes"]
    part = await client.get(rec["audio_url"], headers={"Range": "bytes=0-3"})
    assert part.status_code == 206 and part.content == b"RIFF"
    assert part.headers["content-range"] == f"bytes 0-3/{rec['size_bytes']}"
    bad = await client.get(rec["audio_url"], headers={"Range": f"bytes={rec['size_bytes'] + 10}-"})
    assert bad.status_code == 416

    r = await client.patch(f"/api/recordings/{rid}", json={"listened": True})
    assert r.json()["listened"] is True

    # filters
    assert (await client.get(f"/api/recordings?contact_id={grandma['id']}")).json()[0]["id"] == rid
    assert (await client.get("/api/recordings?contact_id=999")).json() == []
    assert (await client.get("/api/recordings?kind=secret")).json() == []

    # backup bookkeeping
    status = (await client.get("/api/system/status")).json()
    assert status["backup"] == {"last_ok_at": None, "pending": 1}
    assert status["asterisk"] == "connected" and status["phone"] == "registered"
    assert status["trunk"] == "registered"
    pending = (await client.get("/api/system/backup/pending")).json()
    assert pending[0]["id"] == rid and pending[0]["path"].endswith(f"call-{call['id']}.wav")
    r = await client.post("/api/system/backup-report", json={"ids": [rid]})
    assert r.json()["marked"] == 1
    assert (await client.get("/api/recordings?backed_up=false")).json() == []
    status = (await client.get("/api/system/status")).json()
    assert status["backup"]["pending"] == 0 and status["backup"]["last_ok_at"]


async def test_recording_path_layout(client, rt, ari, grandma):
    call = await make_call(client, rt, ari)
    with rt.db.session() as s:
        from tincan.models import Recording

        rec = s.get(Recording, call["recording_id"])
        path = rec.path
    year, month, name = path.split("/")
    assert len(year) == 4 and len(month) == 2 and name == f"call-{call['id']}.wav"
    assert (rt.config.recordings_dir / path).exists()
    assert rec.sha256 and len(rec.sha256) == 64


async def test_calls_pagination(client, rt, ari, grandma):
    await client.patch(
        "/api/settings",
        json={"daily_call_cap": 0, "max_call_minutes": 1, "warning_seconds_before_end": 0},
    )
    for _ in range(3):
        ari.dial("2")
        await settle(rt, timeout=5)
    page = (await client.get("/api/calls?limit=2")).json()
    assert [c["id"] for c in page] == [3, 2]
    nxt = (await client.get(f"/api/calls?limit=2&before={page[-1]['id']}")).json()
    assert [c["id"] for c in nxt] == [1]
