# Runs automatically on boot. Prints each input change and lights the LED while any is pressed.
import time
from machine import Pin

from inputs import Inputs
from pinmap import PINS

led = Pin("LED", Pin.OUT)
inputs = Inputs(PINS)
print("pi-phone: listening on", PINS)

while True:
    for name, pressed in inputs.events():
        print(name, "down" if pressed else "up")
    led.value(inputs.any_pressed())
    time.sleep_ms(5)
