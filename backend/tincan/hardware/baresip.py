"""baresip control over its `ctrl_tcp` module.

Wire format: netstrings (`<len>:<payload>,`) carrying JSON. We send
`{"command": "dial", "params": "sip:2@127.0.0.1", "token": "<id>"}` and read back
`{"response": true, "ok": true, "data": "...", "token": "<id>"}` plus unsolicited
`{"event": true, "type": "CALL_INCOMING", "class": "call", "peeruri": "...", ...}` events.
Commands used: `dial`, `accept`, `hangup`, `sndcode` (DTMF). The event names are baresip's
`ua_event` names; see phone/README.md for the exact set in the packaged version.

Reconnects with backoff forever; `connected` tells the state machine whether dialing can work.
UNTESTED AGAINST A REAL baresip as of 2026-10-30.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from tincan.hardware.base import PhoneEvent

log = logging.getLogger(__name__)

EVENT_MAP = {
    "CALL_INCOMING": "incoming",
    "CALL_ESTABLISHED": "established",
    "CALL_CLOSED": "closed",
}


def encode_netstring(payload: bytes) -> bytes:
    return f"{len(payload)}:".encode() + payload + b","


class BaresipClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 4444, timeout: float = 5.0):
        self.host, self.port, self.timeout = host, port, timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._events: asyncio.Queue[PhoneEvent] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._seq = itertools.count(1)
        self._closed = False
        self._task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    # -- connection -----------------------------------------------------------------------------

    async def _connect_loop(self) -> None:
        delay = 1.0
        while not self._closed:
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout
                )
                log.info("baresip ctrl_tcp connected at %s:%s", self.host, self.port)
                self._events.put_nowait(PhoneEvent("connected"))
                delay = 1.0
                await self._read_loop()
            except (OSError, TimeoutError) as exc:
                log.warning("baresip ctrl_tcp at %s:%s unavailable: %s", self.host, self.port, exc)
            finally:
                if self._writer is not None:
                    self._writer.close()
                    self._writer = self._reader = None
                    self._events.put_nowait(PhoneEvent("disconnected"))
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(ConnectionError("baresip disconnected"))
                self._pending.clear()
            if not self._closed:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 15.0)

    async def _read_netstring(self) -> bytes:
        assert self._reader is not None
        head = await self._reader.readuntil(b":")
        length = int(head[:-1])
        payload = await self._reader.readexactly(length + 1)
        if payload[-1:] != b",":
            raise ConnectionError("bad netstring terminator")
        return payload[:-1]

    async def _read_loop(self) -> None:
        while True:
            raw = await self._read_netstring()
            try:
                msg = json.loads(raw)
            except ValueError:
                log.warning("baresip sent non-JSON: %r", raw[:100])
                continue
            if msg.get("response"):
                fut = self._pending.pop(str(msg.get("token", "")), None)
                if fut is not None and not fut.done():
                    fut.set_result(msg)
            elif msg.get("event"):
                kind = EVENT_MAP.get(str(msg.get("type", "")))
                if kind is not None:
                    self._events.put_nowait(PhoneEvent(kind, msg.get("peeruri")))

    # -- commands -------------------------------------------------------------------------------

    async def command(self, command: str, params: str | None = None) -> dict[str, Any]:
        if self._writer is None:
            raise ConnectionError("baresip not connected")
        token = str(next(self._seq))
        body: dict[str, Any] = {"command": command, "token": token}
        if params is not None:
            body["params"] = params
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[token] = fut
        self._writer.write(encode_netstring(json.dumps(body).encode()))
        await self._writer.drain()
        try:
            reply = await asyncio.wait_for(fut, self.timeout)
        finally:
            self._pending.pop(token, None)
        if not reply.get("ok", True):
            raise RuntimeError(f"baresip {command} failed: {reply.get('data')}")
        return reply

    async def dial(self, uri: str) -> None:
        await self.command("dial", uri)

    async def answer(self) -> None:
        await self.command("accept")

    async def hangup(self) -> None:
        await self.command("hangup")

    async def send_dtmf(self, digit: str) -> None:
        await self.command("sndcode", digit)

    async def events(self) -> AsyncIterator[PhoneEvent]:
        if self._task is None:
            self._task = asyncio.create_task(self._connect_loop(), name="baresip-ctrl")
        while not self._closed:
            yield await self._events.get()

    async def close(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._writer is not None:
            self._writer.close()
