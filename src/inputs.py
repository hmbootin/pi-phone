# Debounced switch inputs. Each switch sits between a GPIO and GND and uses the internal
# pull-up, so a pin reads 0 while its switch is closed. (Pull-ups, not pull-downs: RP2350
# erratum E9 makes the internal pull-downs latch high.)
import time
from machine import Pin

DEBOUNCE_MS = 20


class Input:
    def __init__(self, name, gpio):
        self.name = name
        self.pin = Pin(gpio, Pin.IN, Pin.PULL_UP)
        self.pressed = False
        self._raw = False
        self._changed_at = time.ticks_ms()

    def poll(self, now):
        """Return True if the debounced state just changed."""
        raw = self.pin.value() == 0
        if raw != self._raw:
            self._raw = raw
            self._changed_at = now
        elif raw != self.pressed and time.ticks_diff(now, self._changed_at) >= DEBOUNCE_MS:
            self.pressed = raw
            return True
        return False


class Inputs:
    def __init__(self, pins):
        self.inputs = [Input(name, gpio) for name, gpio in pins.items()]

    def events(self):
        """Yield (name, pressed) for each input whose debounced state changed."""
        now = time.ticks_ms()
        for i in self.inputs:
            if i.poll(now):
                yield i.name, i.pressed

    def any_pressed(self):
        return any(i.pressed for i in self.inputs)
