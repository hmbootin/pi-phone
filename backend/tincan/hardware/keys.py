"""Key names on the LD-858 keypad and what the state machine does with each.

Key names are the strings the scanner reports and the parent UI shows. Dialable keys double as
the Asterisk extension baresip dials (`sip:m1@asterisk`), which is why memory keys are lowercase
and digit-free (see asterisk/etc/extensions.conf and tincan.schemas.MEMORY_KEYS).
"""

from __future__ import annotations

from dataclasses import dataclass

DIGITS = tuple(str(d) for d in range(10))
MEMORY_KEYS = tuple(f"m{i}" for i in range(1, 10)) + ("sos",)
#: Keys that start a call when pressed with dial tone: their name is the extension dialed.
DIALABLE = DIGITS + MEMORY_KEYS
#: Keys passed through as DTMF during a call (digits plus the two symbols).
DTMF = DIGITS + ("*", "#")
#: Keys the phone has but Tin Can ignores (the phone's own line features).
IGNORED = ("store", "speaker", "redial", "flash")
ALL_KEYS = DIALABLE + ("*", "#") + IGNORED


@dataclass(frozen=True)
class KeyEvent:
    key: str
    pressed: bool  # False on release


@dataclass(frozen=True)
class HookEvent:
    off_hook: bool  # True when the handset is lifted


InputEvent = KeyEvent | HookEvent


def is_dialable(key: str) -> bool:
    return key in DIALABLE


def is_dtmf(key: str) -> bool:
    return key in DTMF
