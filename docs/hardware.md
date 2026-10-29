# Hardware

## Board

- Raspberry Pi Pico 2 W (RP2350 + CYW43439 Wi-Fi/Bluetooth).
- Firmware: MicroPython v1.29.0 (`RPI_PICO2_W`).
- USB VID:PID `2e8a:0005`, serial `2f46a57efadbd63a`. Shows up as `/dev/cu.usbmodem*`.
- Onboard LED is `Pin("LED")`. It's wired to the Wi-Fi chip, not a GPIO.

## Connecting from the host

`mise.toml` sets `PICO=id:<serial>` and every task runs `mpremote connect $PICO`. Connecting by USB
serial is stable across ports and hubs. Bare `mpremote` (`connect auto`) takes the first `usbmodem`
it finds, which on the dev machine is an LG monitor's USB controller, and fails with
"could not enter raw repl".

To use a different board, update `PICO` in `mise.toml` with the serial from `mpremote connect list`
(second column).

Only one process can hold the serial port. Close any REPL or Thonny before running tasks.

## Flashing firmware

`picotool` comes from Homebrew (`brew install picotool`). It isn't in the mise registry.

1. Put the board in bootloader mode: hold BOOTSEL while plugging in, or `mise run mp bootloader`.
   A blank board boots into the bootloader on its own.
2. Download the `.uf2` from https://micropython.org/download/RPI_PICO2_W/.
3. `picotool load -x <file>.uf2`

Drag-and-drop onto the RP2350 drive doesn't work on the dev machine: macOS sees the drive but
won't mount it. `picotool` writes over USB without mounting it.

## Wiring

Each input is a switch between a GPIO and GND, using the internal pull-up (active low).
`src/pinmap.py` is the source of truth for which GPIO each input uses. Avoid GP23–25 and GP29:
the Pico W uses them for the wireless chip.

Breadboard test: push buttons stand in for phone keys. Put a button across the center channel,
one leg to the GPIO and the diagonal leg to a GND pin (physical pins 3, 8, 13, 18, 23, 28, 33, 38).
No resistor needed.

| Input | GPIO | Physical pin |
|-------|------|--------------|
| 1–4   | GP2–GP5 | 4–7 |
| 5–8   | GP6–GP9 | 9–12 |
| 9, 0  | GP10, GP11 | 14, 15 |
| hook  | GP15 | 20 |
