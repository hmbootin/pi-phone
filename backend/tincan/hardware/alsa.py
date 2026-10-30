"""Local audio with `aplay`: tones into the handset (USB adapter) and the ringer (Pi jack).

Two independent players. The handset one loops a file until stopped; the ringer plays the
ringtone burst, waits the off time, and repeats. Both kill their aplay on stop so a hangup never
leaves a tone running. Volume is applied with `amixer` on the ringer card when a control name is
configured; otherwise it is left to alsamixer.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class _Player:
    def __init__(self, device: str, name: str):
        self.device = device
        self.name = name
        self._task: asyncio.Task[None] | None = None
        self._proc: asyncio.subprocess.Process | None = None

    async def _play_once(self, path: Path) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            "aplay",
            "-q",
            "-D",
            self.device,
            str(path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await self._proc.communicate()
        if self._proc.returncode not in (0, -15, -9):
            log.warning(
                "%s: aplay %s failed: %s", self.name, path.name, err.decode(errors="replace")[-200:]
            )
        self._proc = None

    async def _loop(self, path: Path, repeat: bool, gap: float) -> None:
        try:
            while True:
                await self._play_once(path)
                if not repeat:
                    return
                if gap:
                    await asyncio.sleep(gap)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("%s player died", self.name)

    async def start(self, path: Path, repeat: bool, gap: float = 0.0) -> None:
        await self.stop()
        self._task = asyncio.create_task(self._loop(path, repeat, gap), name=f"aplay-{self.name}")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        if self._proc is not None and self._proc.returncode is None:
            try:
                self._proc.terminate()
            except ProcessLookupError:
                pass
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


class AlsaAudio:
    def __init__(
        self,
        handset_device: str = "plughw:1,0",
        ringer_device: str = "plughw:0,0",
        ringer_mixer: str | None = None,
    ):
        self.handset = _Player(handset_device, "handset")
        self.ringer = _Player(ringer_device, "ringer")
        self.ringer_mixer = ringer_mixer  # e.g. "PCM" or "Headphone"; None = leave alone

    async def play_handset(self, path: Path, loop: bool = False) -> None:
        await self.handset.start(path, repeat=loop)

    async def stop_handset(self) -> None:
        await self.handset.stop()

    async def ring(self, path: Path, on_seconds: float, off_seconds: float, volume: int) -> None:
        if self.ringer_mixer:
            card = self.ringer.device.split(":", 1)[-1].split(",", 1)[0]
            proc = await asyncio.create_subprocess_exec(
                "amixer", "-q", "-c", card, "sset", self.ringer_mixer, f"{volume}%",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            await proc.wait()
        await self.ringer.start(path, repeat=True, gap=off_seconds)

    async def stop_ring(self) -> None:
        await self.ringer.stop()

    async def close(self) -> None:
        await self.stop_ring()
        await self.stop_handset()
