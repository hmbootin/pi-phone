# Architecture

## The one-paragraph version

A cheap corded landline phone is gutted and its four useful parts are wired to a **Raspberry Pi 4**:
the keypad and hook switch go to GPIO, the handset's mic and earpiece go to a USB audio adapter,
and the phone's own base speaker becomes the ringer through a small amp on the Pi's headphone jack.
A tiny SIP client on the Pi (**baresip**, the `phone` service) turns that handset audio into a SIP
phone that registers to **Asterisk**, also on the Pi. Asterisk doesn't decide anything; it hands
every call to the **tincan backend** (Python) through ARI, Asterisk's REST + WebSocket control API.
The backend also owns the hardware: it scans the keys, watches the hook, plays ringtones, and tells
baresip when to dial, answer and hang up. It applies policy (allowed contacts, time caps,
do-not-disturb, quiet hours) and either bridges the call to a family member through a **SIP trunk
provider** (which gives us a real phone number) or runs a local **feature** (weather, fun fact,
secret message). Asterisk records both sides of every bridged call to disk; a background job backs
recordings up off-site and sends notifications. Parents manage all of it from a small web app on
the home network (or anywhere via Tailscale).

## Why this shape

- **Intercepting audio is free.** Because every call is bridged inside Asterisk, both audio legs are
  already in software. `MixMonitor` writes a mixed (or stereo, one leg per channel) recording with
  one line of config. No taps on wires, no second sound card.
- **No phone line anywhere.** The phone's line-side electronics (48 V loop, 90 V ring, DTMF dialer,
  hybrid) are bypassed, not re-created. Keys are switches, the handset is a USB headset, the ringer
  is a WAV file. Nothing in the device exceeds 5 V. See [ADR 0002](adr/0002-direct-phone-interface.md)
  and [hardware/phone-interface.md](../hardware/phone-interface.md).
- **Asterisk still sees a phone.** baresip is a stock SIP client; Asterisk, the trunk, recording and
  every call flow are the same as with any SIP handset. The backend is the only thing that knows
  the phone is made of GPIO pins.
- **Policy lives in one place.** The backend is the only thing that knows about contacts and rules.
  Asterisk config never changes at runtime, so there is nothing to reload and nothing to corrupt.
- **Cloud only where unavoidable.** See [ADR 0004](adr/0004-sip-trunk-provider.md) and
  [ADR 0006](adr/0006-cloud-boundary.md).

## Components

| Component | Runs where | Tech | Owns |
|-----------|-----------|------|------|
| Phone | desk | gutted `LD-858` corded phone: 26-key matrix, hook switch, handset mic + earpiece, base speaker | the toddler's half |
| Interface | inside/beside the phone | USB audio adapter (CM108), PAM8403 amp, 1 kΩ per GPIO line | analog ↔ Pi |
| phone service | Pi, container | baresip, ALSA, `ctrl_tcp` | SIP registration as `phone`, RTP ↔ handset audio, DTMF |
| Asterisk | Pi, container | Asterisk 20 LTS, chan_pjsip, ARI | SIP registration (phone + trunk), RTP, bridging, recording, audio playback |
| backend | Pi, container | Python 3.12, FastAPI, SQLite, httpx/websockets ARI client, gpiozero | key/hook scanning, ringer, baresip control, call routing, policies, features, contacts, recordings index, parent API, notifications |
| ui | built into backend image | React, Vite, TS | parent app |
| ops | Pi host | Docker Compose, systemd timers, rclone, Tailscale | updates, backups, remote access |
| trunk provider | cloud | Telnyx or VoIP.ms (Twilio supported, needs port forward) | the public phone number, PSTN in/out |

## Call flows

### Toddler calls Grandma (speed dial 2, or memory key M1)

1. Toddler lifts handset. The backend's hook scanner sees off-hook and plays dial tone into the
   handset (a local WAV on the USB adapter; baresip is idle).
2. Toddler presses `2` (or `M1`). The key scanner reports it; the backend stops dial tone and tells
   baresip to dial `sip:2@127.0.0.1` (memory keys map to their own extensions, `m1`..`m9`, `sos`).
3. Asterisk `extensions.conf` context `from-phone` matches and runs `Stasis(tincan,dial,2)`.
4. Backend receives `StasisStart`, looks up speed dial `2` → contact "Grandma", checks:
   contact enabled, not on DND, within quiet hours, no concurrent call, daily call count under cap.
5. Backend plays a short ring-back/"calling Grandma" prompt, originates `PJSIP/+1555...@trunk` with
   caller ID set to our number, and on answer bridges the two channels and starts `MixMonitor`
   (stereo: phone on the left, far end on the right).
6. A timer counts down the max duration. At T-60 s a soft beep plays to both sides. At T-0 the
   backend plays "bye bye!" and hangs up.
7. Hook goes on-hook → backend tells baresip to hang up. On hangup the backend writes a call record
   (contact, start, duration, recording path, outcome) and queues the recording for backup.

### Grandma calls the toddler

1. Trunk provider sends `INVITE` to Asterisk, context `from-trunk`, which does `Stasis(tincan,inbound)`.
2. Backend checks caller ID against contacts. Unknown callers get a polite recording and hangup (or
   voicemail-to-parent if enabled). Known contact outside allowed hours gets "it's sleepy time" and a
   notification to the parent.
3. Backend originates `PJSIP/phone`. baresip reports the incoming call; the backend plays the
   ringtone on the base speaker in a 2 s / 4 s cadence.
4. Toddler lifts handset → backend tells baresip to answer → bridge, record, time cap, same as above.
   No answer in 25 s → "they're busy, try later" to the caller, and a missed-call notification to
   parents.

### Toddler presses 7 (fun fact)

1. Same entry as above; the backend sees speed dial 7 is mapped to feature `fun_fact`.
2. The feature picks a fact for the configured topic, synthesizes speech with Piper (on-device TTS)
   into an 8 kHz WAV in the cache, and the backend plays it on the channel via ARI.
3. Hangup. Features never leave the Pi.

### Toddler presses 8 (secret message for Mom)

1. Backend plays "tell Mom your secret, then hang up", records the channel until hangup, saves it as
   a recording of kind `secret`, backs it up, and sends a push notification with a link.

### Keys that are not calls

Pressing a key on-hook does nothing audible by default. Keys the backend does not map (STORE,
REDIAL, FLASH, SPEAKER) are ignored. A key pressed during a call is sent as a DTMF event through
baresip, which the backend may use later for in-call features.

## Data

- `contacts`: name, display name for prompts, phone number (E.164) or SIP URI, speed dial digit or
  memory key, enabled, inbound allowed, DND-until, per-contact max duration override, avatar prompt audio.
- `features`: key → feature id + config JSON (topic, greeting text).
- `settings`: max call minutes, quiet hours, daily call cap, notification targets, trunk caller ID,
  ringtone, ringer volume.
- `calls`: one row per attempt, including rejected ones, with reason.
- `recordings`: path, kind (call/secret/voicemail), duration, backed_up_at, sha256.

Everything is in one SQLite file at `/data/tincan.db`. Audio lives under `/data/recordings/` and
`/data/prompts/`. Both are on the Pi's SSD/SD, both are backed up.

## Hardware access from containers

- `backend` gets `/dev/gpiochip0` (keys, hook, LED) and `/dev/snd` (ringer on the Pi's headphone
  jack, dial tone on the USB adapter while baresip is idle).
- `phone` (baresip) gets `/dev/snd` for the USB adapter and talks SIP to Asterisk over loopback
  (both on host networking).
- Fakes for all three (ARI, GPIO, baresip control) are used in tests and in `mise run demo`.

## Networking

- Everything SIP-side lives on the Pi: baresip registers to Asterisk over loopback as PJSIP
  endpoint `phone`.
- Asterisk registers outbound to the trunk provider; inbound comes over the same registration, so no
  port forwarding is needed. RTP range 10000-10100 only matters if you later use direct SIP contacts.
- Tailscale on the Pi gives parents the UI from anywhere and gives developers (and Claude Code on a
  laptop) SSH without exposing anything to the internet.

## Where the time goes when something breaks

- Nothing in the earpiece: USB audio adapter missing or wrong ALSA device. `aplay -l`, then
  `docker compose logs phone`. Then `pjsip show endpoints` for registration.
- Keys do nothing: `docker compose logs backend` for the scanner; check the GPIO bundle.
- Dials but nothing happens: backend not connected to ARI. `docker compose logs backend`.
- Calls connect but one side is silent: RTP/NAT between Pi and trunk. Check `rtp set debug on`.
  If the toddler can hear but not be heard, it's the mic: `alsamixer` capture gain.
- No ring: `aplay` a WAV to the headphone jack on the host; check the amp's 5 V.
- Recording missing: `/data/recordings` mount or permissions.

See [runbook.md](runbook.md).
