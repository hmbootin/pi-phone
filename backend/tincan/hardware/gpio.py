"""Keypad matrix + hook switch on the Pi's GPIO, via gpiozero (imported lazily: laptops lack it).

Scanning runs in a thread at `pinmap.scan_hz`: drive one column low, read every row, release the
column, next column. A key is reported once it has read the same for `debounce_ms`. The hook pin
is read the same way. Events are handed to the asyncio loop with call_soon_threadsafe.

UNTESTED ON HARDWARE as of 2026-10-30: written against hardware/phone-interface.md section 5.1
and the gpiozero API. scripts/keyscan.py exercises exactly this class on the bench.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import AsyncIterator

from tincan.hardware.keys import HookEvent, InputEvent, KeyEvent
from tincan.hardware.pinmap import PinMap

log = logging.getLogger(__name__)


class GpioInputs:
    def __init__(self, pinmap: PinMap):
        from gpiozero import DigitalInputDevice, DigitalOutputDevice  # type: ignore[import-not-found]

        self.pinmap = pinmap
        self._rows = [DigitalInputDevice(p, pull_up=True) for p in pinmap.rows]
        self._cols = [
            DigitalOutputDevice(p, active_high=False, initial_value=False) for p in pinmap.cols
        ]
        self._hook = DigitalInputDevice(pinmap.hook, pull_up=True)
        self._queue: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pressed: set[str] = set()
        self._off_hook = self._read_hook()

    # -- raw reads -------------------------------------------------------------------------------

    def _read_hook(self) -> bool:
        closed = not self._hook.value  # pull-up: LOW (value 0) means the switch is closed
        return not closed if self.pinmap.hook_closed_when_down else closed

    def _read_keys(self) -> set[str]:
        down: set[str] = set()
        for c, col in enumerate(self._cols, start=1):
            col.on()  # active_high=False: "on" drives the line low
            time.sleep(0.0002)
            for r, row in enumerate(self._rows, start=1):
                if not row.value:
                    key = self.pinmap.key_at(r, c)
                    if key is not None:
                        down.add(key)
            col.off()
        return down

    # -- Inputs interface -------------------------------------------------------------------------

    def off_hook(self) -> bool:
        return self._off_hook

    def _emit(self, ev: InputEvent) -> None:
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._queue.put_nowait, ev)

    def _scan(self) -> None:
        period = 1.0 / self.pinmap.scan_hz
        stable_for = self.pinmap.debounce_ms / 1000.0
        last_keys, keys_since = self._read_keys(), time.monotonic()
        last_hook, hook_since = self._read_hook(), time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            keys = self._read_keys()
            if keys != last_keys:
                last_keys, keys_since = keys, now
            elif keys != self._pressed and now - keys_since >= stable_for:
                for k in sorted(keys - self._pressed):
                    self._emit(KeyEvent(k, True))
                for k in sorted(self._pressed - keys):
                    self._emit(KeyEvent(k, False))
                self._pressed = keys
            hook = self._read_hook()
            if hook != last_hook:
                last_hook, hook_since = hook, now
            elif hook != self._off_hook and now - hook_since >= stable_for:
                self._off_hook = hook
                self._emit(HookEvent(hook))
            time.sleep(max(0.0, period - (time.monotonic() - now)))

    async def events(self) -> AsyncIterator[InputEvent]:
        self._loop = asyncio.get_running_loop()
        if self._thread is None:
            self._thread = threading.Thread(target=self._scan, name="keyscan", daemon=True)
            self._thread.start()
        while not self._stop.is_set():
            yield await self._queue.get()

    async def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        for dev in (*self._rows, *self._cols, self._hook):
            dev.close()
