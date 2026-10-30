from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from tests.fake_ari import TestAri
from tincan import store
from tincan.ari.fake import CAUSE_NORMAL
from tincan.config import Config
from tincan.main import create_app
from tincan.runtime import Runtime
from tincan.schemas import Settings
from tincan.tts.piper import Tts

PASSWORD = "parent-pw"


class RecordingTts(Tts):
    """Remembers every text rendered so tests can assert on what was said."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.rendered: list[str] = []

    async def render(self, text: str) -> Path:
        self.rendered.append(text)
        return await super().render(text)


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        tincan_data_dir=tmp_path / "data",
        tincan_fake_ari=True,
        tincan_time_scale=0.01,
        tincan_parent_password=PASSWORD,
        tincan_secret_key="test-secret",
        piper_bin="definitely-not-installed-piper",
        _env_file=None,
    )


@pytest.fixture
async def app(config: Config):
    application = create_app(config)
    rt: Runtime = application.state.runtime
    # Swap in the test flavour of the fake with a TTS that records what was said.
    rt.fake = TestAri(recordings_dir=config.recordings_dir)
    rt.ari = rt.fake
    rt.tts = RecordingTts(config.prompts_dir, piper_bin=config.piper_bin)
    # Tests must not depend on the wall clock: no quiet hours unless a test sets them.
    store.save_settings(rt.db, Settings(quiet_hours=None))
    await rt.start()
    await asyncio.sleep(0)  # let the router consume AriConnected
    yield application
    await rt.stop()


@pytest.fixture
def rt(app) -> Runtime:
    return app.state.runtime


@pytest.fixture
def ari(rt) -> TestAri:
    return rt.fake


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/auth/login", json={"password": PASSWORD})
        assert r.status_code == 200
        yield c


@pytest.fixture
async def anon(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def grandma(client) -> dict:
    r = await client.post(
        "/api/contacts",
        json={
            "name": "Grandma",
            "spoken_name": "Grandma Jo",
            "number": "+15555550123",
            "speed_dial": 2,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def settle(rt: Runtime, timeout: float = 3.0) -> None:
    """Wait until every call session has finished and been written."""
    await rt.router.wait_idle(timeout)


async def calls(client) -> list[dict]:
    r = await client.get("/api/calls")
    assert r.status_code == 200
    return r.json()


__all__ = ["CAUSE_NORMAL", "calls", "settle"]
