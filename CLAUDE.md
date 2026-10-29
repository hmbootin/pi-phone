# pi-phone

MicroPython app for a Raspberry Pi Pico 2 W that turns an old landline phone into a control interface.

- `src/` mirrors the board's filesystem; `src/main.py` runs on boot.
- Code runs on MicroPython, not CPython: use `machine`, `time.sleep_ms`, etc. No pip; board packages come from `mip`.
- Board setup, flashing, and wiring live in `docs/hardware.md`. Read it only for hardware or firmware work.

## Commands

- `mise run try [file]` runs a file on the board without saving it (default `src/main.py`). Use this to iterate.
- `mise run deploy` copies `src/` to the board and restarts it.
- `mise run mp <mpremote args>` for anything else, e.g. `mise run mp exec "print(1)"`.
- Don't run `mise run repl` (needs a TTY) or bare `mpremote` (connects to the wrong device).
- "could not enter raw repl" usually means another process holds the serial port.
