# pi-phone

An old landline phone wired to a Raspberry Pi Pico 2 W, used as a control interface.

## Setup

1. `mise install` installs `mpremote`.
2. Flash MicroPython onto the board if it's new. See [docs/hardware.md](docs/hardware.md).
3. Set `PICO` in `mise.toml` to your board's serial (`mpremote connect list`).

## Usage

```
mise run try        # run src/main.py on the board without saving it
mise run deploy     # copy src/ to the board and restart
mise tasks          # list all tasks
```
