"""Load hardware/pinmap.toml: which GPIO is which keypad row/column, the hook switch, the keys."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from tincan.hardware.keys import ALL_KEYS

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "hardware" / "pinmap.toml"


@dataclass(frozen=True)
class PinMap:
    rows: tuple[int, ...]  # BCM numbers, inputs with pull-up
    cols: tuple[int, ...]  # BCM numbers, driven low one at a time
    hook: int  # BCM number, input with pull-up
    hook_closed_when_down: bool  # True: switch reads LOW (closed) when the handset is on the cradle
    keys: dict[str, tuple[int, int]] = field(default_factory=dict)  # key -> (row, col), 1-based
    scan_hz: float = 100.0
    debounce_ms: int = 20
    led: int | None = None

    def key_at(self, row: int, col: int) -> str | None:
        for key, (r, c) in self.keys.items():
            if (r, c) == (row, col):
                return key
        return None


def load(path: Path | str = DEFAULT_PATH) -> PinMap:
    data = tomllib.loads(Path(path).read_text())
    gpio, keys = data["gpio"], data.get("keys", {})
    rows = tuple(int(x) for x in gpio["rows"])
    cols = tuple(int(x) for x in gpio["cols"])
    parsed: dict[str, tuple[int, int]] = {}
    seen: dict[tuple[int, int], str] = {}
    for key, rc in keys.items():
        if key not in ALL_KEYS:
            raise ValueError(f"pinmap: unknown key {key!r}")
        r, c = int(rc[0]), int(rc[1])
        if not (1 <= r <= len(rows) and 1 <= c <= len(cols)):
            raise ValueError(
                f"pinmap: key {key!r} at ({r},{c}) is outside the {len(rows)}x{len(cols)} matrix"
            )
        if (r, c) in seen:
            raise ValueError(f"pinmap: keys {seen[(r, c)]!r} and {key!r} share ({r},{c})")
        seen[(r, c)] = key
        parsed[key] = (r, c)
    return PinMap(
        rows=rows,
        cols=cols,
        hook=int(gpio["hook"]),
        hook_closed_when_down=bool(gpio.get("hook_closed_when_down", True)),
        keys=parsed,
        scan_hz=float(data.get("scan", {}).get("hz", 100)),
        debounce_ms=int(data.get("scan", {}).get("debounce_ms", 20)),
        led=int(gpio["led"]) if gpio.get("led") is not None else None,
    )
