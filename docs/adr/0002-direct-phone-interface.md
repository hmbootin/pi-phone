# 0002 Wire the phone directly to the Pi: GPIO for keys and hook, USB audio for the handset

Status: accepted. 2026-10-30.

An analog phone normally needs a "line": ~48 V DC through ~600 Ω, off-hook detection by loop
current, ~90 V RMS at 20 Hz to ring, DTMF decoding, and a hybrid to split the 2-wire audio into
send and receive. Anything that provides that (an ATA box, or a SLIC module plus firmware) exists
only so the phone's line-side electronics can keep doing their job.

We have a specific phone (board `LD-858SOSBMB`: line-powered, 26-key big-button speakerphone, no
screen) and we are willing to gut it. So we skip the line entirely and connect the phone's
transducers and switches to the Pi with ordinary interfaces:

- keypad matrix (26 keys, ~11 lines) and hook switch → GPIO, scanned by the backend;
- handset electret mic and receiver → a CM108-class USB audio adapter (which supplies mic bias);
- the phone's base speaker → a PAM8403 amp on the Pi 4's headphone jack, for ringtones.

The phone's own ICs (ringer, dialer, speech network, speakerphone) are left unpowered; one chip is
removed so it cannot load the key lines. See `hardware/phone-interface.md`.

Why this over an ATA (Grandstream HT801, ~$35, no soldering): about $35 of parts, no 48 V or 90 V
anywhere a toddler can reach, custom ringtones from a real speaker, key events available without
going off-hook, and the memory keys become named speed dials. The cost is ~15 solder joints, a
software phone leg on the Pi, and echo/sidetone becoming our problem instead of the ATA's DSP.

Why this over a SLIC module (Ag1171/KS0835F): the SLIC path re-creates the line so the phone's
electronics can stay; that is weeks of analog debugging to end up where GPIO and a USB codec start.

Consequences:

- Asterisk still sees a SIP phone. A `phone` service (baresip, ALSA audio, `ctrl_tcp` control)
  registers as the PJSIP endpoint `phone`. ARI, policy, recording and features are unchanged.
- The backend gains a hardware service (key/hook scanner, ringer player, baresip client) with fakes
  for tests, alongside `fake_ari.py`.
- The phone is not swappable without a new keypad map. Fine: it is the one phone.
- The Pico firmware in `firmware/pico/` is not needed; GPIO on the Pi does what it did.
