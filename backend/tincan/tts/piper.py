"""Text to speech with Piper, cached as 8 kHz 16-bit mono WAV under <data>/prompts.

Asterisk plays `sound:<path without extension>` and expects 8 kHz for `.wav`. If the `piper`
binary is missing (dev laptops) the cache entry becomes a copy of beep.wav and a warning is
logged, so every flow still produces audible output.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import struct
import wave
from pathlib import Path

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
BEEP = STATIC_DIR / "beep.wav"
SILENCE = STATIC_DIR / "silence.wav"
TARGET_RATE = 8000


class Tts:
    def __init__(
        self,
        prompts_dir: Path,
        piper_bin: str = "piper",
        voice: str = "en_US-lessac-medium",
        data_dir: Path | None = None,
    ):
        self.prompts_dir = prompts_dir
        self.piper_bin = piper_bin
        self.voice = voice
        self.data_dir = data_dir
        self._piper_path = shutil.which(piper_bin)
        self._warned = False
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def available(self) -> bool:
        return self._piper_path is not None

    def cache_name(self, text: str) -> str:
        return hashlib.sha256(f"{self.voice}\n{text}".encode()).hexdigest()[:32]

    def cache_path(self, text: str) -> Path:
        return self.prompts_dir / f"{self.cache_name(text)}.wav"

    def media_uri(self, path: Path) -> str:
        """ARI media URI for a WAV on the shared mount (Asterisk adds the extension)."""
        return f"sound:{path.with_suffix('')}"

    async def render(self, text: str) -> Path:
        """Return the cached WAV for `text`, rendering it first if needed."""
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        out = self.cache_path(text)
        if out.exists():
            return out
        lock = self._locks.setdefault(out.name, asyncio.Lock())
        async with lock:
            if out.exists():
                return out
            tmp = out.with_suffix(".tmp.wav")
            if self._piper_path is None:
                if not self._warned:
                    log.warning("piper binary %r not found; prompts will be a beep", self.piper_bin)
                    self._warned = True
                shutil.copyfile(BEEP, tmp)
            else:
                try:
                    await self._run_piper(text, tmp)
                except Exception as exc:  # noqa: BLE001 - never leave the toddler in silence
                    log.error("piper failed (%s); using beep for %r", exc, text)
                    shutil.copyfile(BEEP, tmp)
            tmp.replace(out)
            return out

    async def _run_piper(self, text: str, out: Path) -> None:
        raw = out.with_suffix(".raw.wav")
        cmd = [self._piper_path or self.piper_bin, "-m", self.voice, "-f", str(raw)]
        if self.data_dir is not None:
            cmd += ["--data-dir", str(self.data_dir)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await asyncio.wait_for(proc.communicate(text.encode()), timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(err.decode(errors="replace")[-300:])
        await asyncio.to_thread(convert_to_8k_mono, raw, out)
        raw.unlink(missing_ok=True)


def convert_to_8k_mono(src: Path, dst: Path) -> None:
    """Resample any 16-bit PCM WAV to 8 kHz mono with linear interpolation (no numpy on the Pi)."""
    with wave.open(str(src), "rb") as w:
        channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"expected 16-bit PCM, got {width * 8}-bit")
    n = len(frames) // (2 * channels)
    samples = struct.unpack(f"<{n * channels}h", frames[: n * channels * 2])
    if channels > 1:
        samples = [sum(samples[i * channels : (i + 1) * channels]) // channels for i in range(n)]
    out: list[int] = []
    if rate == TARGET_RATE:
        out = list(samples)
    else:
        step = rate / TARGET_RATE
        total = int(n / step)
        for i in range(total):
            pos = i * step
            j = int(pos)
            frac = pos - j
            a = samples[j]
            b = samples[j + 1] if j + 1 < n else a
            out.append(int(a + (b - a) * frac))
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TARGET_RATE)
        w.writeframes(struct.pack(f"<{len(out)}h", *out))


def wav_duration_seconds(path: Path) -> int | None:
    try:
        with wave.open(str(path), "rb") as w:
            return round(w.getnframes() / w.getframerate())
    except (OSError, wave.Error):
        return None
