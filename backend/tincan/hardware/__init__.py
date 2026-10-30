"""The phone as hardware: keys, hook switch, handset audio, ringer and the baresip client.

Everything behind three small interfaces (`base.py`) with fakes (`fake.py`) so the state machine
(`machine.py`) is fully tested without a wire. The only hardware-specific tables are the key
names in `keys.py` and the GPIO map in `hardware/pinmap.toml` at the repo root.
"""

from tincan.hardware.base import Audio, Inputs, Phone
from tincan.hardware.machine import PhoneState, PhoneStateMachine

__all__ = ["Audio", "Inputs", "Phone", "PhoneState", "PhoneStateMachine"]
