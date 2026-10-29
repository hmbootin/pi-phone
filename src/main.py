# Runs automatically on boot. Placeholder until phone hardware is wired up.
import time
from machine import Pin

led = Pin("LED", Pin.OUT)

for _ in range(3):
    led.toggle()
    time.sleep(0.2)
led.off()
print("pi-phone: booted")
