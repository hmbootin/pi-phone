#!/usr/bin/env python3
"""Stage-2 bench test: print every key press and hook change from the real GPIO scanner.

Run on the Pi, from the repo root, with the breadboard wired per hardware/phone-interface.md 5.1
and hardware/pinmap.toml filled in from the section 3 measurements:

    uv run --project backend python scripts/keyscan.py [path/to/pinmap.toml]

Pass criteria (phone-interface.md stage 2): every key prints exactly once per press, two keys in
the same row both print (no ghosting), lifting/replacing the handset prints offhook/onhook once.
This drives backend/tincan/hardware/gpio.py directly, so a pass here is a pass for the backend.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from tincan.hardware import pinmap
from tincan.hardware.gpio import GpioInputs
from tincan.hardware.keys import HookEvent, KeyEvent


async def main(path: Path) -> None:
    pm = pinmap.load(path)
    print(f"pinmap: {len(pm.rows)} rows {pm.rows}, {len(pm.cols)} cols {pm.cols}, hook GPIO{pm.hook}")
    print(f"{len(pm.keys)} keys mapped; scanning at {pm.scan_hz:.0f} Hz, debounce {pm.debounce_ms} ms")
    inputs = GpioInputs(pm)
    print("hook:", "offhook" if inputs.off_hook() else "onhook", "(at start). Ctrl-C to stop.")
    t0 = time.monotonic()
    try:
        async for ev in inputs.events():
            t = time.monotonic() - t0
            if isinstance(ev, KeyEvent):
                print(f"{t:8.3f}  {ev.key:8s} {'press' if ev.pressed else 'release'}")
            elif isinstance(ev, HookEvent):
                print(f"{t:8.3f}  {'offhook' if ev.off_hook else 'onhook'}")
    finally:
        await inputs.close()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else pinmap.DEFAULT_PATH
    try:
        asyncio.run(main(target))
    except KeyboardInterrupt:
        pass
