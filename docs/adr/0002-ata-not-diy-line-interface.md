# 0002 Use an ATA for the analog line; DIY SLIC is a v2 tinker path

Status: accepted. 2026-10-29.

An analog phone needs a "line" that supplies ~48 V DC through ~600 Ω, detects off-hook by loop
current, superimposes ~90 V RMS 20 Hz to ring, decodes DTMF or pulse dialing, and converts the single
2-wire audio pair into separate send/receive paths (the hybrid). That is a SLIC (subscriber line
interface circuit) plus a codec plus firmware. See `docs/signal-path.md`.

Options considered:

1. **ATA (analog telephone adapter), e.g. Grandstream HT801.** ~$35. Contains the SLIC, codec, echo
   canceller, DTMF and pulse detection, and a SIP stack. Plugs into Ethernet. Zero soldering, and the
   phone's audio becomes an RTP stream Asterisk can bridge and record. Chosen for v1.
2. **SLIC module (Silvertel Ag1171 or the KS0835F "SLIC module" sold for Arduino) + USB sound card +
   Pico/Pi GPIO.** ~$20. All of the above in software: generate ring by toggling the module's ring
   pin, detect off-hook from its status pin, decode pulses or DTMF ourselves, and route audio through
   ALSA into Asterisk via `chan_alsa`/`chan_console` or a custom SIP user agent. It's the better
   learning project and the Pico code already does the hook/dial half. It's also weeks of debugging
   echo and levels before the first call. Documented as v2 in `hardware/diy-line-interface.md`.
3. **Pi telephony HAT with FXS port.** They exist but are rare and expensive, and still need SLIC
   drivers. Not worth it over an ATA.

Consequence: the Pico firmware is not on the v1 critical path. It stays in the repo for v2 and for
optional extra buttons that aren't on the dial (a big "call Mom" button, for example), which it can
report to the backend over Wi-Fi.
