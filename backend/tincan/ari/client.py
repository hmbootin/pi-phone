"""Minimal async ARI client: REST over httpx, events over a WebSocket with reconnect.

Every id (channel, bridge, playback, recording name) is chosen by the caller, so a session can
register its event waiter *before* issuing the request and never miss the completion event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets

from tincan.ari.events import AriConnected, AriDisconnected, AriEvent, parse_event

log = logging.getLogger(__name__)


class AriError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"ARI {status}: {message}")
        self.status = status


class AriClient:
    def __init__(self, url: str, user: str, password: str, app: str):
        self.base = url.rstrip("/")
        self.user = user
        self.password = password
        self.app = app
        self.connected = False
        self._closed = False
        self._http = httpx.AsyncClient(
            base_url=f"{self.base}/ari", auth=(user, password), timeout=10.0
        )

    # -- events -------------------------------------------------------------------------------

    async def events(self) -> AsyncIterator[AriEvent]:
        """Yield events forever, reconnecting with exponential backoff (1s..30s)."""
        scheme = "wss" if self.base.startswith("https") else "ws"
        host = self.base.split("://", 1)[1]
        url = (
            f"{scheme}://{host}/ari/events?app={self.app}&subscribeAll=true"
            f"&api_key={self.user}:{self.password}"
        )
        backoff = 1.0
        while not self._closed:
            try:
                async with websockets.connect(url, max_size=4 * 1024 * 1024) as ws:
                    self.connected = True
                    backoff = 1.0
                    log.info("ARI websocket connected to %s", self.base)
                    yield AriConnected()
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            log.warning("bad ARI frame: %r", raw[:200])
                            continue
                        yield parse_event(data)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - any transport failure means reconnect
                log.warning("ARI websocket error: %s", exc)
            if self.connected:
                self.connected = False
                yield AriDisconnected()
            if self._closed:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def close(self) -> None:
        self._closed = True
        await self._http.aclose()

    # -- REST ---------------------------------------------------------------------------------

    async def _req(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        ok404: bool = False,
    ) -> Any:
        r = await self._http.request(method, path, params=params)
        if r.status_code == 404 and ok404:
            return None
        if r.status_code >= 400:
            raise AriError(r.status_code, r.text[:300])
        if r.content:
            try:
                return r.json()
            except ValueError:
                return None
        return None

    async def answer(self, channel_id: str) -> None:
        await self._req("POST", f"/channels/{channel_id}/answer", ok404=True)

    async def ring(self, channel_id: str) -> None:
        await self._req("POST", f"/channels/{channel_id}/ring", ok404=True)

    async def hangup(self, channel_id: str) -> None:
        await self._req("DELETE", f"/channels/{channel_id}", ok404=True)

    async def get_channel(self, channel_id: str) -> dict[str, Any] | None:
        return await self._req("GET", f"/channels/{channel_id}", ok404=True)

    async def originate(
        self,
        endpoint: str,
        app_args: str,
        channel_id: str,
        caller_id: str | None = None,
        timeout: int = 30,
    ) -> None:
        params: dict[str, Any] = {
            "endpoint": endpoint,
            "app": self.app,
            "appArgs": app_args,
            "channelId": channel_id,
            "timeout": timeout,
        }
        if caller_id:
            params["callerId"] = caller_id
        await self._req("POST", "/channels", params)

    async def play(self, channel_id: str, media: str, playback_id: str) -> None:
        await self._req("POST", f"/channels/{channel_id}/play/{playback_id}", {"media": media})

    async def play_bridge(self, bridge_id: str, media: str, playback_id: str) -> None:
        await self._req("POST", f"/bridges/{bridge_id}/play/{playback_id}", {"media": media})

    async def stop_playback(self, playback_id: str) -> None:
        await self._req("DELETE", f"/playbacks/{playback_id}", ok404=True)

    async def create_bridge(self, bridge_id: str) -> None:
        await self._req("POST", f"/bridges/{bridge_id}", {"type": "mixing"})

    async def add_to_bridge(self, bridge_id: str, *channel_ids: str) -> None:
        await self._req(
            "POST", f"/bridges/{bridge_id}/addChannel", {"channel": ",".join(channel_ids)}
        )

    async def destroy_bridge(self, bridge_id: str) -> None:
        await self._req("DELETE", f"/bridges/{bridge_id}", ok404=True)

    async def record_bridge(self, bridge_id: str, name: str, max_seconds: int = 0) -> None:
        # ARI bridge recordings are a single mixed mono file. Stereo (one leg per channel) is a
        # MixMonitor option that ARI does not expose; see backend/README.md.
        await self._req(
            "POST",
            f"/bridges/{bridge_id}/record",
            {
                "name": name,
                "format": "wav",
                "ifExists": "overwrite",
                "maxDurationSeconds": max_seconds,
                "maxSilenceSeconds": 0,
            },
        )

    async def record_channel(
        self,
        channel_id: str,
        name: str,
        max_seconds: int = 120,
        max_silence: int = 0,
        beep: bool = True,
    ) -> None:
        await self._req(
            "POST",
            f"/channels/{channel_id}/record",
            {
                "name": name,
                "format": "wav",
                "ifExists": "overwrite",
                "maxDurationSeconds": max_seconds,
                "maxSilenceSeconds": max_silence,
                "beep": "true" if beep else "false",
                "terminateOn": "none",
            },
        )

    async def stop_recording(self, name: str) -> None:
        await self._req("POST", f"/recordings/live/{name}/stop", ok404=True)

    async def get_endpoint(self, tech: str, resource: str) -> dict[str, Any] | None:
        return await self._req("GET", f"/endpoints/{tech}/{resource}", ok404=True)
