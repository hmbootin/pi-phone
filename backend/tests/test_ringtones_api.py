from __future__ import annotations

import io
import math
import struct
import wave

from tincan.sounds import BUILTIN_RINGTONES, DIAL_TONE, ringtone_path


def make_wav(seconds: float = 0.5, rate: int = 44100, channels: int = 2, width: int = 2) -> bytes:
    """A small sine WAV in whatever shape the test needs."""
    buf = io.BytesIO()
    n = int(rate * seconds)
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        if width == 2:
            samples = [int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(n)]
            interleaved = [s for s in samples for _ in range(channels)]
            w.writeframes(struct.pack(f"<{n * channels}h", *interleaved))
        else:
            w.writeframes(bytes(n * channels * width))
    return buf.getvalue()


def upload(client, filename: str, data: bytes):
    return client.post("/api/ringtones", files={"file": (filename, data, "audio/wav")})


async def test_list_includes_builtins(client):
    r = await client.get("/api/ringtones")
    assert r.status_code == 200
    by_name = {t["name"]: t for t in r.json()}
    assert set(BUILTIN_RINGTONES) <= set(by_name)
    for name in BUILTIN_RINGTONES:
        t = by_name[name]
        assert t["builtin"] is True
        assert t["audio_url"] == f"/api/ringtones/{name}/audio"
        assert 1.9 <= t["duration_seconds"] <= 2.1
    assert DIAL_TONE.is_file()


async def test_builtin_preview_serves_wav(client):
    r = await client.get("/api/ringtones/classic/audio")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    with wave.open(io.BytesIO(r.content), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
    r = await client.get("/api/ringtones/nope/audio")
    assert r.status_code == 404


async def test_upload_list_preview_delete_round_trip(client, config):
    r = await upload(client, "My Jingle (v2).WAV", make_wav(seconds=1.5, rate=44100, channels=2))
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["name"] == "my-jingle-v2"
    assert entry["builtin"] is False
    assert abs(entry["duration_seconds"] - 1.5) < 0.05
    assert entry["audio_url"] == "/api/ringtones/my-jingle-v2/audio"
    assert (config.data_dir / "ringtones" / "my-jingle-v2.wav").is_file()

    r = await client.get("/api/ringtones")
    names = [t["name"] for t in r.json()]
    assert names[: len(BUILTIN_RINGTONES)] == list(BUILTIN_RINGTONES)
    assert "my-jingle-v2" in names

    r = await client.get("/api/ringtones/my-jingle-v2/audio")
    assert r.status_code == 200
    with wave.open(io.BytesIO(r.content), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        assert abs(w.getnframes() / 16000 - 1.5) < 0.05

    # Overwriting an upload is allowed.
    r = await upload(client, "my-jingle-v2.wav", make_wav(seconds=0.3, rate=8000, channels=1))
    assert r.status_code == 201 and abs(r.json()["duration_seconds"] - 0.3) < 0.05

    r = await client.patch("/api/settings", json={"ringtone": "my-jingle-v2"})
    assert r.status_code == 200 and r.json()["ringtone"] == "my-jingle-v2"
    assert ringtone_path(r.json()["ringtone"], config.data_dir).name == "my-jingle-v2.wav"

    r = await client.delete("/api/ringtones/my-jingle-v2")
    assert r.status_code == 204
    assert not (config.data_dir / "ringtones" / "my-jingle-v2.wav").exists()
    r = await client.get("/api/ringtones")
    assert "my-jingle-v2" not in [t["name"] for t in r.json()]
    r = await client.delete("/api/ringtones/my-jingle-v2")
    assert r.status_code == 404


async def test_delete_active_upload_resets_setting(client, config):
    assert (await upload(client, "bells.wav", make_wav())).status_code == 201
    r = await client.patch("/api/settings", json={"ringtone": "bells"})
    assert r.status_code == 200
    r = await client.delete("/api/ringtones/bells")
    assert r.status_code == 204
    r = await client.get("/api/settings")
    assert r.json()["ringtone"] == "classic"
    # And the resolver never returns a missing file.
    assert ringtone_path("bells", config.data_dir) == BUILTIN_RINGTONES["classic"]


async def test_builtins_cannot_be_deleted_or_overwritten(client):
    r = await client.delete("/api/ringtones/classic")
    assert r.status_code == 409 and r.json()["error"]["code"] == "ringtone_builtin"
    r = await upload(client, "chime.wav", make_wav())
    assert r.status_code == 409 and r.json()["error"]["code"] == "ringtone_builtin"


async def test_rejects_bad_uploads(client):
    r = await upload(client, "notes.wav", b"this is not a wav file at all")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_wav"
    r = await upload(client, "eightbit.wav", make_wav(width=1))
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_wav"
    r = await upload(client, "long.wav", make_wav(seconds=10.5, rate=8000, channels=1))
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_long"
    r = await upload(client, "big.wav", make_wav(seconds=6, rate=96000, channels=2))  # 2.3 MB
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_large"
    r = await upload(client, "---.wav", make_wav())
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_name"
    r = await client.get("/api/ringtones")
    assert all(t["builtin"] for t in r.json())


async def test_settings_rejects_unknown_ringtone(client):
    r = await client.get("/api/settings")
    assert r.json()["ringtone"] == "classic" and r.json()["ringer_volume"] == 80
    r = await client.patch("/api/settings", json={"ringtone": "does-not-exist"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_ringtone"
    assert "does-not-exist" in r.json()["error"]["message"]
    r = await client.patch("/api/settings", json={"ringtone": "Bad Name!"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_settings"
    r = await client.patch("/api/settings", json={"ringer_volume": 101})
    assert r.status_code == 400
    r = await client.patch("/api/settings", json={"ringtone": "birds", "ringer_volume": 55})
    assert r.status_code == 200
    assert r.json()["ringtone"] == "birds" and r.json()["ringer_volume"] == 55


def test_ringtone_path_falls_back_to_classic(tmp_path, config):
    assert ringtone_path("chime", tmp_path) == BUILTIN_RINGTONES["chime"]
    assert ringtone_path("nope", tmp_path) == BUILTIN_RINGTONES["classic"]
    assert ringtone_path("../../etc/passwd", tmp_path) == BUILTIN_RINGTONES["classic"]
    assert ringtone_path(None, tmp_path) == BUILTIN_RINGTONES["classic"]
    from tincan.schemas import Settings

    assert ringtone_path(Settings(ringtone="birds"), tmp_path) == BUILTIN_RINGTONES["birds"]
