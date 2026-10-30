# Architecture

## The one-paragraph version

A cheap analog phone plugs into an **ATA** (analog telephone adapter), a small box whose FXS port
pretends to be the phone company: it supplies line power, generates ring voltage, decodes the dial,
and turns the 2-wire audio into a SIP/RTP stream. That stream goes over Ethernet to **Asterisk**
running on a Raspberry Pi 4. Asterisk doesn't decide anything; it hands every call to the
**tincan backend** (Python) through ARI, Asterisk's REST + WebSocket control API. The backend looks
at what was dialed, applies policy (allowed contacts, time caps, do-not-disturb, quiet hours), and
either bridges the call to a family member through a **SIP trunk provider** (which gives us a real
phone number) or runs a local **feature** (weather, fun fact, secret message). Asterisk records both
sides of every bridged call to disk; a background job backs recordings up off-site and sends
notifications. Parents manage all of it from a small web app on the home network (or anywhere via
Tailscale).

## Why this shape

- **Intercepting audio is free.** Because every call is bridged inside Asterisk, both audio legs are
  already in software. `MixMonitor` writes a mixed (or stereo, one leg per channel) recording with
  one line of config. No taps on wires, no second sound card.
- **The phone is unmodified.** The ATA handles the nasty analog parts (48 V loop current, 90 V ring,
  hybrid echo, DTMF/pulse detection). The toddler's phone can be swapped for any other landline.
  A DIY line interface (SLIC module + Pico) is a documented v2 path, not a prerequisite.
- **Policy lives in one place.** The backend is the only thing that knows about contacts and rules.
  Asterisk config never changes at runtime, so there is nothing to reload and nothing to corrupt.
- **Cloud only where unavoidable.** See [ADR 0004](adr/0004-sip-trunk-provider.md) and
  [ADR 0006](adr/0006-cloud-boundary.md).

## Components

| Component | Runs where | Tech | Owns |
|-----------|-----------|------|------|
| Phone + ATA | desk | Grandstream HT801 (or any FXS ATA with SIP) | analog line, dial decode, ring |
| Asterisk | Pi, container | Asterisk 20 LTS, chan_pjsip, ARI | SIP registration (ATA + trunk), RTP, bridging, recording, audio playback |
| backend | Pi, container | Python 3.12, FastAPI, SQLite, httpx/websockets ARI client | call routing, policies, features, contacts, recordings index, parent API, notifications |
| ui | built into backend image | React, Vite, TS | parent app |
| ops | Pi host | Docker Compose, systemd timers, rclone, Tailscale | updates, backups, remote access |
| trunk provider | cloud | Telnyx or VoIP.ms (Twilio supported, needs port forward) | the public phone number, PSTN in/out |

## Call flows

### Toddler calls Grandma (speed dial 2)

1. Toddler lifts handset. ATA closes the loop, plays dial tone locally.
2. Toddler presses `2`. ATA's dial plan is set to send single digits immediately (`{x}` pattern, no
   inter-digit timeout), so it sends `INVITE sip:2@pi`.
3. Asterisk `extensions.conf` context `from-phone` matches `_X` and runs `Stasis(tincan,dial,2)`.
4. Backend receives `StasisStart`, looks up speed dial `2` → contact "Grandma", checks:
   contact enabled, not on DND, within quiet hours, no concurrent call, daily call count under cap.
5. Backend plays a short ring-back/"calling Grandma" prompt, originates `PJSIP/+1555...@trunk` with
   caller ID set to our number, and on answer bridges the two channels and starts `MixMonitor`
   (stereo: phone on the left, far end on the right).
6. A timer counts down the max duration. At T-60 s a soft beep plays to both sides. At T-0 the
   backend plays "bye bye!" and hangs up.
7. On hangup the backend writes a call record (contact, start, duration, recording path, outcome)
   and queues the recording for backup.

### Grandma calls the toddler

1. Trunk provider sends `INVITE` to Asterisk, context `from-trunk`, which does `Stasis(tincan,inbound)`.
2. Backend checks caller ID against contacts. Unknown callers get a polite recording and hangup (or
   voicemail-to-parent if enabled). Known contact outside allowed hours gets "it's sleepy time" and a
   notification to the parent.
3. Backend originates `PJSIP/phone` (the ATA). The ATA generates ring voltage; the phone physically rings.
4. Toddler picks up → bridge, record, time cap, same as above. No answer in 25 s → "they're busy,
   try later" to the caller, and a missed-call notification to parents.

### Toddler presses 7 (fun fact)

1. Same entry as above; the backend sees speed dial 7 is mapped to feature `fun_fact`.
2. The feature picks a fact for the configured topic, synthesizes speech with Piper (on-device TTS)
   into an 8 kHz WAV in the cache, and the backend plays it on the channel via ARI.
3. Hangup. Features never leave the Pi.

### Toddler presses 8 (secret message for Mom)

1. Backend plays "tell Mom your secret, then hang up", records the channel until hangup, saves it as
   a recording of kind `secret`, backs it up, and sends a push notification with a link.

## Data

- `contacts`: name, display name for prompts, phone number (E.164) or SIP URI, speed dial digit,
  enabled, inbound allowed, DND-until, per-contact max duration override, avatar prompt audio.
- `features`: digit → feature id + config JSON (topic, greeting text).
- `settings`: max call minutes, quiet hours, daily call cap, notification targets, trunk caller ID.
- `calls`: one row per attempt, including rejected ones, with reason.
- `recordings`: path, kind (call/secret/voicemail), duration, backed_up_at, sha256.

Everything is in one SQLite file at `/data/tincan.db`. Audio lives under `/data/recordings/` and
`/data/prompts/`. Both are on the Pi's SSD/SD, both are backed up.

## Networking

- ATA and Pi on the same LAN. ATA registers to Asterisk as a PJSIP endpoint `phone`.
- Asterisk registers outbound to the trunk provider; inbound comes over the same registration, so no
  port forwarding is needed. RTP range 10000-10100 only matters if you later use direct SIP contacts.
- Tailscale on the Pi gives parents the UI from anywhere and gives developers (and Claude Code on a
  laptop) SSH without exposing anything to the internet.

## Where the time goes when something breaks

- No dial tone: ATA power/registration. Look at Asterisk `pjsip show endpoints`.
- Dials but nothing happens: backend not connected to ARI. `docker compose logs backend`.
- Calls connect but one side is silent: RTP/NAT between Pi and trunk. Check `rtp set debug on`.
- Recording missing: `/data/recordings` mount or permissions.

See [runbook.md](runbook.md).
