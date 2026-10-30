#!/usr/bin/env python3
"""Generate the backend's built-in tones and ringtones as 16-bit PCM mono WAVs.

    uv run --project backend python scripts/gen_tones.py [out_dir]

Pure stdlib (wave, math, struct) and deterministic: running it twice yields identical bytes, so
the committed files in backend/tincan/sounds/ can be regenerated and diffed. No sox, no numpy.

Handset tones are 8 kHz (they go to the USB adapter, same format as the Piper prompts). Ringtones
are 16 kHz (they go to the base speaker through the headphone jack, so a bit more treble helps).
Ring cadence (2 s on / 4 s off) is the player's job: each ringtone is only the 2 s "on" burst.
"""

from __future__ import annotations

import math
import random
import struct
import sys
import wave
from collections.abc import Callable, Sequence
from pathlib import Path

HANDSET_RATE = 8000
RINGER_RATE = 16000
TAU = 2 * math.pi

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "backend" / "tincan" / "sounds"


def dbfs(db: float) -> float:
    return 10 ** (db / 20)


def fade(samples: list[float], rate: int, ms: float) -> None:
    """Linear fade in and out over `ms` so loops and starts never click."""
    n = min(len(samples) // 2, int(rate * ms / 1000))
    for i in range(n):
        g = i / n
        samples[i] *= g
        samples[-1 - i] *= g


def render(rate: int, seconds: float, fn: Callable[[float], float]) -> list[float]:
    return [fn(i / rate) for i in range(int(rate * seconds))]


Voice = tuple[float, Callable[[float], float]]


def mix(rate: int, seconds: float, voices: Sequence[Voice]) -> list[float]:
    """Sum of voices, each (start_seconds, fn(t since start)), silent before their start."""
    out = [0.0] * int(rate * seconds)
    for start, fn in voices:
        first = int(start * rate)
        for i in range(first, len(out)):
            out[i] += fn((i - first) / rate)
    return out


def pluck(
    freq: float, length: float, decay: float = 4.0, gain: float = 1.0
) -> Callable[[float], float]:
    """A soft bell-ish note: fundamental plus a quieter, faster-decaying octave, 10 ms attack."""

    def fn(t: float) -> float:
        if t >= length:
            return 0.0
        attack = min(1.0, t / 0.01)
        env = attack * math.exp(-decay * t)
        octave = 0.25 * math.exp(-decay * t) * math.sin(TAU * 2 * freq * t)
        return gain * env * (math.sin(TAU * freq * t) + octave)

    return fn


def write_wav(path: Path, rate: int, samples: list[float]) -> None:
    peak = max(1e-9, max(abs(s) for s in samples))
    if peak > 1.0:  # never clip; the levels below are chosen so this does not trigger
        samples = [s / peak for s in samples]
    frames = struct.pack(f"<{len(samples)}h", *(int(round(s * 32767)) for s in samples))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


# ---------------------------------------------------------------- handset tones (8 kHz)


def dial_tone() -> list[float]:
    """North American precise dial tone: 350 Hz + 440 Hz, continuous, about -12 dBFS peak.

    2 s is an integer number of cycles of both tones (700 and 880), so looping is phase-continuous
    even before the 5 ms fade."""
    a = dbfs(-12) / 2
    s = render(HANDSET_RATE, 2.0, lambda t: a * (math.sin(TAU * 350 * t) + math.sin(TAU * 440 * t)))
    fade(s, HANDSET_RATE, 5)
    return s


def call_ended() -> list[float]:
    """Friendly two-note descending chime (E5 then C5) for 'the other side hung up'."""
    g = dbfs(-9)
    high, low = pluck(659.25, 0.6, decay=5, gain=g), pluck(523.25, 0.65, decay=4, gain=g)
    notes = [(0.0, high), (0.35, low)]
    s = mix(HANDSET_RATE, 1.0, notes)
    fade(s, HANDSET_RATE, 5)
    return s


def error_tone() -> list[float]:
    """Soft triple beep for 'could not dial': three 120 ms sine blips at 620 Hz, 160 ms apart."""
    g = dbfs(-12)

    def blip(t: float) -> float:
        if t >= 0.12:
            return 0.0
        env = min(1.0, t / 0.01, (0.12 - t) / 0.02)
        return g * env * math.sin(TAU * 620 * t)

    s = mix(HANDSET_RATE, 1.0, [(0.05, blip), (0.33, blip), (0.61, blip)])
    fade(s, HANDSET_RATE, 5)
    return s


# ---------------------------------------------------------------- ringtones (16 kHz, 2 s bursts)


def ring_classic() -> list[float]:
    """Synthesized bell ringer: 1000 Hz and 1200 Hz tones, amplitude-modulated at 20 Hz (the
    clapper), with a touch of their second harmonics for brightness. About -6 dBFS peak."""
    g = dbfs(-6)

    def fn(t: float) -> float:
        mod = 0.55 + 0.45 * math.cos(TAU * 20 * t)
        tone = 0.5 * math.sin(TAU * 1000 * t) + 0.5 * math.sin(TAU * 1200 * t)
        tone += 0.08 * math.sin(TAU * 2000 * t) + 0.08 * math.sin(TAU * 2400 * t)
        return g * mod * tone / 1.16

    s = render(RINGER_RATE, 2.0, fn)
    fade(s, RINGER_RATE, 15)
    return s


def ring_chime() -> list[float]:
    """Gentle C major arpeggio (C5 E5 G5, then C6), each note ringing into the next."""
    g = dbfs(-6) * 0.7
    notes = [(0.0, 523.25), (0.4, 659.25), (0.8, 783.99), (1.2, 1046.5)]
    voices = [(start, pluck(f, 2.0 - start, decay=2.5, gain=g)) for start, f in notes]
    s = mix(RINGER_RATE, 2.0, voices)
    fade(s, RINGER_RATE, 15)
    return s


def ring_birds() -> list[float]:
    """Playful birdsong: short upward chirps (1.8 to 3.6 kHz sweeps) in little flurries. The
    pattern comes from a fixed-seed PRNG so the file is reproducible."""
    rng = random.Random(20261030)
    g = dbfs(-7)
    chirps: list[Voice] = []
    t = 0.05
    while t < 1.8:
        for _ in range(rng.randint(2, 4)):  # a flurry of 2-4 chirps
            f0 = rng.uniform(1800, 2600)
            f1 = f0 * rng.uniform(1.3, 1.6)
            length = rng.uniform(0.05, 0.09)

            def chirp(t: float, f0=f0, f1=f1, length=length) -> float:
                if t >= length:
                    return 0.0
                env = math.sin(math.pi * t / length)  # smooth on and off
                phase = TAU * (f0 * t + (f1 - f0) * t * t / (2 * length))  # linear sweep
                return g * env * math.sin(phase)

            chirps.append((t, chirp))
            t += length + rng.uniform(0.02, 0.06)
        t += rng.uniform(0.15, 0.3)  # breath between flurries
    s = mix(RINGER_RATE, 2.0, chirps)
    fade(s, RINGER_RATE, 10)
    return s


FILES: dict[str, tuple[int, Callable[[], list[float]]]] = {
    "dial_tone.wav": (HANDSET_RATE, dial_tone),
    "call_ended.wav": (HANDSET_RATE, call_ended),
    "error.wav": (HANDSET_RATE, error_tone),
    "ring_classic.wav": (RINGER_RATE, ring_classic),
    "ring_chime.wav": (RINGER_RATE, ring_chime),
    "ring_birds.wav": (RINGER_RATE, ring_birds),
}


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    for name, (rate, fn) in FILES.items():
        path = out_dir / name
        samples = fn()
        write_wav(path, rate, samples)
        print(f"{path}: {rate} Hz, {len(samples) / rate:.2f} s, {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
