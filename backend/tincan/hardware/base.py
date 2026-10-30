"""The three interfaces the state machine talks to. Real and fake implementations share them."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tincan.hardware.keys import InputEvent


class Inputs(Protocol):
    """Key presses and the hook switch, as one event stream."""

    def off_hook(self) -> bool:
        """Current hook state (read at boot; the stream only reports changes)."""
        ...

    def events(self) -> AsyncIterator[InputEvent]: ...

    async def close(self) -> None: ...


class Audio(Protocol):
    """Local audio the backend plays itself: handset tones while baresip is idle, the ringer."""

    async def play_handset(self, path: Path, loop: bool = False) -> None:
        """Start playing into the handset earpiece; returns immediately. Replaces what played."""
        ...

    async def stop_handset(self) -> None: ...

    async def ring(self, path: Path, on_seconds: float, off_seconds: float, volume: int) -> None:
        """Start the ringer cadence on the base speaker; returns immediately."""
        ...

    async def stop_ring(self) -> None: ...

    async def close(self) -> None: ...


@dataclass(frozen=True)
class PhoneEvent:
    """What the SIP client (baresip) reports."""

    kind: str  # "incoming" | "established" | "closed" | "connected" | "disconnected"
    peer: str | None = None


class Phone(Protocol):
    """Control of the SIP client. Every call method must raise on failure, never hang."""

    @property
    def connected(self) -> bool: ...

    async def dial(self, uri: str) -> None: ...

    async def answer(self) -> None: ...

    async def hangup(self) -> None: ...

    async def send_dtmf(self, digit: str) -> None: ...

    def events(self) -> AsyncIterator[PhoneEvent]: ...

    async def close(self) -> None: ...
