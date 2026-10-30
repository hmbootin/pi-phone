# Signal path: from the toddler's mouth to Grandma's ear and back

What happens to sound and signalling at every hop, and where we intercept it. Read this once; it
explains every wire in [hardware/phone-interface.md](../hardware/phone-interface.md) and every
recording option the backend uses.

```
 the phone (gutted)                      Raspberry Pi 4                                        cloud / PSTN
┌────────────────┐  USB   ┌─────────────────────────────────────────────────────────┐  SIP+RTP  ┌───────────┐
│ handset mic    ├───────▶│ USB audio ─▶ baresip ("phone" service) ─SIP/RTP (lo)─▶  │ internet  │ SIP trunk │──▶ Grandma's
│ handset earpiece│◀──────│ adapter  ◀─        ▲ ctrl_tcp                 Asterisk  │◀─────────▶│ provider  │    cell
│ 26 keys, hook  ├─GPIO──▶│ backend ───────────┘                  ┌───────┴───────┐  │  UDP      │ (VoIP.ms, │
│ base speaker   │◀─amp───│ Pi headphone jack (ringtone WAV)      │ bridge        │  │           │  Telnyx…) │
└────────────────┘        │                                       │ phone ⇄ trunk │  │           └───────────┘
                          │                    MixMonitor / ARI ◀─┴───────────────┘  │
                          │                         ▼                                │
                          │   /data/recordings   backend (policy, prompts, Piper TTS) │
                          └─────────────────────────────────────────────────────────┘
```

Two things to keep straight:

- **Signalling** (off-hook, keys, ring, hangup) and **audio** are separate from the very first
  inch: keys and hook are GPIO pins read by the backend, audio is a USB sound card. There is no
  2-wire line, so none of the voltages or tones a phone company line would carry exist here.
- Everything on the Pi is already software. We never tap a wire. "Intercepting both sides" means
  asking Asterisk for the audio it is already mixing.

## 1. Keys and hook (phone ⇄ backend)

The phone's 26 keys are a switch matrix on two small PCBs; the hook switch is a plain microswitch.
The backend scans them through GPIO at 100 Hz: drive one column low, read the rows, next column.
20 ms debounce. Every line has 1 kΩ in series so a toddler mashing several keys at once can never
short two GPIO outputs together.

| Event | What the backend does |
|-------|-----------------------|
| hook off, idle | play dial tone (350 + 440 Hz WAV) into the handset through the USB adapter; start a 10 s "no key" timer |
| key while off-hook and idle | stop dial tone, tell baresip to dial `sip:<key>@127.0.0.1` (`0`-`9`, `m1`-`m9`, `sos`); `*`/`#`/STORE/REDIAL/FLASH/SPEAKER are ignored |
| hook off while ringing | tell baresip to answer; stop the ringtone |
| hook on | tell baresip to hang up (if in a call); stop any tone; back to idle |
| key during a call | forwarded by baresip as an RFC 4733 DTMF event (unused today) |
| hook off at boot | treated as idle off-hook: dial tone, no auto-dial |

A toddler slamming the cradle produces rapid on/off; the backend treats any on-hook longer than
the debounce as a hangup and never a "flash".

## 2. Handset audio (phone ⇄ baresip)

- **Mic**: an electret capsule in the handset. The USB audio adapter puts 2-4.5 V of plug-in power
  on the mic tip through a few kΩ, which is the bias an electret needs; the capsule's FET modulates
  that into a few mV of audio. The adapter's codec (CM108) samples it at 48 kHz, 16-bit; baresip
  resamples to 8 kHz.
- **Earpiece**: a ~150 Ω dynamic receiver on the adapter's headphone output. Software volume sits
  around 60 %; a toddler-safe cap.
- **Sidetone** (hearing yourself in the earpiece) is what the phone's speech network used to do.
  baresip can mix a little mic into the earpiece in software; off by default, the toddler won't miss it.
- **Echo**: the handset's mic and earpiece are acoustically separate, so there is no hybrid leak
  and nothing to cancel on our side. Any echo Grandma hears is acoustic (earpiece → mic in the
  handset) and tiny.

## 3. Dialing

There are no DTMF tones. A key is a GPIO event; the backend turns it into a SIP `INVITE` by asking
baresip (`ctrl_tcp`, JSON over a local socket) to dial. Asterisk sees `INVITE sip:2@<pi>` from
endpoint `phone` within ~30 ms of the key.

Memory keys and SOS are extensions of their own (`m1`..`m9`, `sos`) so a contact can be bound to a
key with a name on it rather than a digit the toddler must remember. `from-phone` in
`extensions.conf` matches `_X` and `_[ms].` and sends everything to `Stasis(tincan,dial,${EXTEN})`.

## 4. Sampling and coding (inside baresip)

- The USB adapter runs at 48 kHz; baresip's audio pipeline band-limits and resamples to **8 kHz**,
  16-bit mono.
- **G.711 µ-law (PCMU)** compands each sample to 8 bits: **64 kbit/s**, no compression delay,
  what the PSTN itself uses, so transcoding to the trunk is free. baresip is configured for ulaw
  only; `allow=ulaw` on both Asterisk endpoints keeps one codec end to end.
- Samples are packed **20 ms per RTP packet** (160 samples, 160 bytes + 12-byte RTP + 8 UDP +
  20 IP = 200 bytes, 50 packets/s each direction). Over loopback this costs nothing.
- Silence suppression/VAD off: comfort noise makes a toddler think the line died.

## 5. SIP and RTP between baresip and Asterisk

Both on the same host, so this is the boring part.

1. baresip registers: `REGISTER sip:127.0.0.1` as user `phone` with digest auth. Asterisk stores
   the contact (`pjsip show contacts`) and pings it with `OPTIONS` every `qualify_frequency` seconds.
2. Toddler presses 7: `INVITE sip:7@127.0.0.1` with an SDP offer (PCMU, telephone-event).
3. Asterisk answers `200 OK` with its own RTP port; from then on two UDP streams flow over
   loopback. `direct_media=no` on the endpoint keeps RTP anchored in Asterisk, which is
   what lets us record it.
4. Hangup from either side is a `BYE`.

Inbound (Asterisk ringing the phone) is the same with roles swapped: Asterisk sends `INVITE
sip:phone@127.0.0.1`, baresip answers `180 Ringing` and reports the call to the backend, which
plays the ringtone on the base speaker until the hook lifts; then baresip sends `200 OK`.

## 6. What Asterisk does with the two legs

Every call enters the dialplan and immediately runs `Stasis(tincan, …)`, which parks the channel
in the backend's ARI application. The backend then:

1. **Plays prompts** on the single channel (`POST /channels/{id}/play` with `sound:` or a Piper
   WAV at 8 kHz mono). Audio is injected into the channel's read side; nothing else is involved.
2. **Originates the second leg** (`POST /channels` with `endpoint=PJSIP/+1555…@trunk`, or
   `PJSIP/phone`, i.e. baresip, for inbound) into the same Stasis app.
3. **Creates a mixing bridge** (`POST /bridges?type=mixing`) and adds both channels. Asterisk
   now runs a mixer: for each 20 ms tick it takes the phone's frame, the trunk's frame, and
   writes "everyone but you" to each. With exactly two parties and the same codec, Asterisk
   picks the **native RTP bridge** path (packet passthrough, no decode) unless something needs
   the audio, such as recording or DTMF detection. Recording forces the **simple/softmix bridge**
   path, which decodes to 8 kHz signed linear in software. That costs nothing on a Pi 4.
4. **Ends it**: `DELETE /channels/{id}` on either leg or on the timer.

## 7. Recording both sides

Three mechanisms; the backend uses the first for calls and the second for prompts-and-record
features. All write to **`/var/spool/asterisk/recording/`** (ARI) or
**`/var/spool/asterisk/monitor/`** (MixMonitor), which the Compose file bind-mounts to
`/data/recordings/`.

### a. Bridge recording (mixed mono, simplest)

`POST /bridges/{id}/record?name=calls/2026-10-29T15-01-02_grandma&format=wav&ifExists=overwrite&maxDurationSeconds=0&beep=false`

Captures the mixed audio of everyone in the bridge into one mono WAV. `RecordingStarted` /
`RecordingFinished` events arrive on the ARI WebSocket; a hangup stops and stores it automatically.
Good enough for a "memories" archive.

### b. Channel recording (one party only)

`POST /channels/{id}/record?name=secret/…&format=wav&maxSilenceSeconds=4&terminateOn=#`

Records only what that channel sends. Used for "secret message for Mom" and voicemail. **A channel
cannot be recorded with this call while it is in a bridge** (Asterisk refuses); for per-leg
recording during a call, see (c).

### c. Per-leg ("stereo") recording via snoop channels

To get phone on the left and Grandma on the right:

1. `POST /channels/{phone}/snoop?spy=in&app=tincan&appArgs=snoop` → a snoop channel that hears
   only what the phone *sends*.
2. `POST /channels/{trunk}/snoop?spy=in&…` → same for the far end.
3. `POST /channels/{snoop}/record?name=…_L&format=wav` on each.
4. After the call, `sox -M L.wav R.wav stereo.wav` (the backup job can do this).

That is exactly what the dialplan application does in one line, if you prefer to start it from
`extensions.conf` before `Stasis()` (MixMonitor cannot be started from ARI; it can from the
dialplan or AMI):

```
same => n,MixMonitor(${UNIQUEID}.wav,b,r(${UNIQUEID}_in.wav)t(${UNIQUEID}_out.wav))
```

- first argument: the mixed file (optional when `r`/`t` are given)
- `b`: only record while bridged (so prompts and dial tone aren't in the "call" file; do **not**
  use `b` for features, nothing is bridged)
- `r(file)`: the **receive** feed (what the phone sends into Asterisk); `t(file)`: the
  **transmit** feed (what Asterisk sends to the phone, i.e. Grandma)
- the two files are kept sample-aligned by inserting silence; `n` disables that. (Older docs call
  the sync flag `S`; in Asterisk 20 sync is the default and only `n` exists.)
- `D` writes an interleaved 2-channel **raw** stream instead (must use `.raw`), which is the only
  single-file stereo MixMonitor produces; `sox -r 8000 -e signed -b 16 -c 2 x.raw x.wav` fixes it.

Formats: `wav` = 16-bit signed PCM at 8 kHz (128 kbit/s, ~1 MB/min); `wav49`/`WAV` = GSM-in-WAV
(13 kbit/s, telephone quality); `sln` = headerless. Keep `wav`; disk is cheap, memories aren't.

### Where to find the file

- ARI names are relative to `/var/spool/asterisk/recording/`; subdirectories in the name are
  allowed and created. `GET /recordings/stored/{name}` and `DELETE` work on them.
- MixMonitor names are relative to `/var/spool/asterisk/monitor/` unless absolute.
- The backend stores the final path and sha256 in the `recordings` table and the backup job
  copies it off-site.

## 8. Latency budget (mouth to ear)

| Hop | Typical | Notes |
|-----|---------|-------|
| Handset → USB adapter → ALSA | 10-20 ms | USB audio period size; baresip default 20 ms buffers |
| baresip packetization | 20 ms | one frame must fill before it can be sent |
| Asterisk jitter buffer + mixing | 20-60 ms | adaptive jitter buffer on the trunk leg; loopback leg needs none |
| Pi → provider | 10-40 ms | depends on which POP you pick; choose the nearest |
| Provider → PSTN → cell network | 100-250 ms | mobile networks add the most; nothing we can do |
| Far-end phone jitter buffer + decode | 20-80 ms | |
| **Total one way** | **~180-470 ms** | ITU G.114 says <150 ms is unnoticed, <400 ms acceptable. Grandma-to-toddler feels like a normal cell call. |

Wi-Fi on the Pi adds jitter, not latency, and jitter is what makes words drop. It is wired for a
reason.

## 9. Phone-service configuration that matters (baresip)

| Goal | Setting | Value |
|------|---------|-------|
| Audio on the USB adapter | `audio_player` / `audio_source` | `alsa,plughw:1,0` |
| One codec end to end | `audio_codecs` / `module` | `g711.so`, PCMU only |
| Digits as events | `dtmf_mode` on the Asterisk endpoint | `rfc4733` |
| Backend control | `module ctrl_tcp.so`, `ctrl_tcp_listen` | `127.0.0.1:4444` |
| Never answer by itself | `auto_answer` | off; the hook switch answers |
| Register to Asterisk | `accounts` | `<sip:phone@127.0.0.1>;auth_pass=$PHONE_SIP_PASSWORD;answermode=manual` |

Ringtone and dial tone are not baresip's: the backend plays them (`aplay`) on the Pi's headphone
jack and the USB adapter respectively, so they can be any WAV a parent uploads.

## 10. How the phone rings on demand

The backend asks Asterisk to **originate** a call to the phone
(`POST /channels?endpoint=PJSIP/phone&app=tincan&appArgs=inbound,…`). Asterisk sends an `INVITE`
to baresip, which answers `180 Ringing` and emits a `CALL_INCOMING` event on `ctrl_tcp`. The
backend starts the ringtone on the base speaker (2 s on / 4 s off, or whatever cadence the
ringtone WAV has; a "Grandma ring" is just a different file per contact). When the toddler lifts
the handset the hook scanner fires, the backend sends baresip `accept`, baresip sends `200 OK`, the
channel enters Stasis, and the backend bridges it to the waiting trunk leg. If nobody answers, the
backend cancels the originate after `ring_timeout_seconds`, baresip gets a `CANCEL`, and the
ringtone stops. The "test call" button in the parent UI is literally this with a prompt instead of
a trunk leg.
