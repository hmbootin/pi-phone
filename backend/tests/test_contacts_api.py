from datetime import UTC, datetime, timedelta


async def test_requires_login(anon):
    r = await anon.get("/api/contacts")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert (await anon.get("/healthz")).status_code == 200
    r = await anon.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "bad_password"


async def test_crud_and_shape(client, grandma):
    assert grandma["speed_dial"] == 2
    assert grandma["spoken_name"] == "Grandma Jo"
    assert grandma["created_at"].endswith("Z")
    assert set(grandma) == {
        "id", "name", "spoken_name", "number", "speed_dial", "memory_key", "enabled",
        "inbound_allowed", "dnd_until", "max_call_minutes", "created_at",
    }  # fmt: skip
    r = await client.get("/api/contacts")
    assert [c["name"] for c in r.json()] == ["Grandma"]

    r = await client.patch(
        f"/api/contacts/{grandma['id']}", json={"max_call_minutes": 3, "enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["max_call_minutes"] == 3 and r.json()["enabled"] is False

    r = await client.delete(f"/api/contacts/{grandma['id']}")
    assert r.status_code == 204
    assert (await client.get("/api/contacts")).json() == []
    assert (await client.delete(f"/api/contacts/{grandma['id']}")).status_code == 404


async def test_speed_dial_conflict(client, grandma):
    r = await client.post(
        "/api/contacts", json={"name": "Mom", "number": "+15555550101", "speed_dial": 2}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "speed_dial_taken"
    r = await client.post(
        "/api/contacts", json={"name": "Mom", "number": "+15555550101", "speed_dial": 1}
    )
    assert r.status_code == 201
    r = await client.patch(f"/api/contacts/{r.json()['id']}", json={"speed_dial": 2})
    assert r.status_code == 409


async def test_number_normalisation_and_validation(client):
    r = await client.post("/api/contacts", json={"name": "Mom", "number": "(555) 555-0101"})
    assert r.status_code == 201 and r.json()["number"] == "+5555550101"
    r = await client.post(
        "/api/contacts", json={"name": "Uncle", "number": "sip:uncle@example.org"}
    )
    assert r.status_code == 201 and r.json()["number"] == "sip:uncle@example.org"
    r = await client.post("/api/contacts", json={"name": "Nobody", "number": "abc"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_dnd(client, grandma):
    cid = grandma["id"]
    r = await client.post(f"/api/contacts/{cid}/dnd", json={"minutes": 120})
    until = datetime.fromisoformat(r.json()["dnd_until"].replace("Z", "+00:00"))
    assert timedelta(minutes=119) < until - datetime.now(UTC) <= timedelta(minutes=120)
    r = await client.post(f"/api/contacts/{cid}/dnd", json={"until": "2030-01-01T00:00:00Z"})
    assert r.json()["dnd_until"] == "2030-01-01T00:00:00Z"
    r = await client.post(f"/api/contacts/{cid}/dnd", json={"clear": True})
    assert r.json()["dnd_until"] is None
    r = await client.post(f"/api/contacts/{cid}/dnd", json={})
    assert r.status_code == 400


async def test_memory_key_crud_and_conflict(client, grandma):
    r = await client.patch(f"/api/contacts/{grandma['id']}", json={"memory_key": "M1"})
    assert r.status_code == 200 and r.json()["memory_key"] == "m1"
    r = await client.post(
        "/api/contacts", json={"name": "Mom", "number": "+15555550101", "memory_key": "m1"}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "memory_key_taken"
    r = await client.post(
        "/api/contacts", json={"name": "Mom", "number": "+15555550101", "memory_key": "sos"}
    )
    assert r.status_code == 201 and r.json()["memory_key"] == "sos"
    assert r.json()["speed_dial"] is None
    r = await client.post(
        "/api/contacts", json={"name": "Nobody", "number": "+15555550102", "memory_key": "m10"}
    )
    assert r.status_code == 422
    r = await client.patch(f"/api/contacts/{grandma['id']}", json={"memory_key": None})
    assert r.status_code == 200 and r.json()["memory_key"] is None
