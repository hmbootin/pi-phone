from tincan.schemas import Settings


async def test_defaults_match_contract(client):
    defaults = Settings().model_dump()
    assert defaults["quiet_hours"] == {"start": "19:30", "end": "07:30", "tz": "America/Chicago"}
    r = await client.get("/api/settings")
    s = r.json()
    assert set(s) == set(defaults)
    assert s["max_call_minutes"] == 10
    assert s["warning_seconds_before_end"] == 60
    assert s["daily_call_cap"] == 10
    assert s["ring_timeout_seconds"] == 25
    assert s["unknown_caller_policy"] == "reject"
    assert s["notifications"] == {"ntfy_topic": None, "email": None}
    assert s["weather_location"]["name"] == "home"


async def test_patch_merges_and_validates(client):
    r = await client.patch("/api/settings", json={"max_call_minutes": 3, "quiet_hours": None})
    assert r.status_code == 200
    assert r.json()["max_call_minutes"] == 3 and r.json()["quiet_hours"] is None
    r = await client.get("/api/settings")
    assert r.json()["max_call_minutes"] == 3
    assert r.json()["daily_call_cap"] == 10

    r = await client.patch("/api/settings", json={"unknown_caller_policy": "shout"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_settings"
    r = await client.patch("/api/settings", json={"nope": 1})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_setting"
    r = await client.patch("/api/settings", json={"notifications": {"ntfy_topic": "tincan-home"}})
    assert r.json()["notifications"] == {"ntfy_topic": "tincan-home", "email": None}
