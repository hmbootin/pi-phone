# Signal path: from the toddler's mouth to Grandma's ear and back

What happens to sound and signalling at every hop, and where we intercept it. Read this once; it
explains every setting in [hardware/ata-setup.md](../hardware/ata-setup.md) and every recording
option the backend uses.

```
 toddler's phone            ATA (Grandstream HT801)            Raspberry Pi 4                  cloud / PSTN
┌──────────────┐  2-wire   ┌──────────────────────┐  SIP+RTP  ┌───────────────────────┐  SIP+RTP  ┌───────────┐
│ carbon/electret│ tip/ring │ SLIC  hybrid  codec  │ Ethernet  │ Asterisk              │ internet  │ SIP trunk │──▶ Grandma's
│ mic + receiver│◀────────▶│ -48V  2w→4w   G.711  │◀─────────▶│  ┌─────────────────┐  │◀─────────▶│ provider  │    cell
│ keypad / bell │  RJ11    │ ring  echo    RTP    │  UDP      │  │ bridge           │  │  UDP      │ (VoIP.ms, │
└──────────────┘          │ gen   cancel  SIP    │           │  │ phone ⇄ trunk    │  │           │  Telnyx…) │
                          └──────────────────────┘           │  └───┬─────────┬───┘  │           └───────────┘
                                                             │  MixMonitor /  ARI    │
                                                             │  snoop+record  events │
                                                             │      ▼           ▼    │
                                                             │ /data/recordings  backend (policy, prompts, Piper TTS)
                                                             └───────────────────────┘
```

Two things to keep straight:

- **Signalling** (off-hook, digits, ring, hangup) and **audio** travel on the *same two wires*
  between phone and ATA, as different voltages/currents. From the ATA onward they are separate:
  SIP (signalling, TCP/UDP 5060) and RTP (audio, UDP 10000-20000).
- Everything on the Pi is already software. We never tap a wire. "Intercepting both sides" means
  asking Asterisk for the audio it is already mixing.

## 1. The 2-wire loop (phone ⇄ ATA)

The ATA's FXS port imitates a phone company central office (CO) line. One pair: **tip** (A) and
**ring** (B), named after the plug on a 1900s switchboard cord.

| State | What the ATA does | What the phone does |
|-------|-------------------|---------------------|
| On-hook (idle) | Supplies **-48 V DC** on ring relative to tip, through ~600 Ω feed. Almost no current flows because the hook switch is open. | Bell/ringer circuit is across the line via a capacitor (blocks DC). |
| Off-hook | The ATA's SLIC sees **loop current** (~20-25 mA; HT801 constant-current feed, and the KS0835F/Ag1171 SLICs in the v2 doc are 23-31 mA) and reports "off-hook". It then plays dial tone (350 + 440 Hz) into the line. | Hook switch closes, putting the handset (mic + receiver) across the line. |
| Ringing | Superimposes **~45-90 V RMS at 20 Hz** on the DC. North American cadence is **2 s on / 4 s off**. The HT801 V2 lets you pick 45/50/55 Vrms ("Ring Power") and the frequency (default 20 Hz); it drives up to 5 REN (five old-style bells). | The ringer (bell or piezo) responds to the AC. |
| Ring trip | The moment loop current appears during ringing, the SLIC stops ringing (ring trip) and reports off-hook. | Toddler lifts handset. |
| Hangup | Loop current stops. The ATA sends SIP `BYE`. Optionally it can drop loop current briefly when the *far* end hangs up ("Loop Current Disconnect") so legacy PBX gear notices; a plain phone doesn't need it. | Handset goes back on the cradle. |

Hook flash is a deliberate 300-1100 ms on-hook blip the phone company used for call waiting and
3-way. A toddler slamming the cradle will produce these constantly, which is why we disable hook
flash and all call features on the ATA (see ata-setup.md).

## 2. The hybrid: 2 wires in, 4 wires out, and why echo exists

The phone sends and receives on the same pair. The ATA (and every phone and every CO line card)
contains a **hybrid**: a transformer or op-amp bridge that subtracts what it is transmitting from
what it sees on the line to recover what the far end is saying. The subtraction is never perfect
because the line impedance is never exactly 600 Ω, so some of the ATA's own transmit signal leaks
back into its receive path. That leak is **echo**: Grandma hears herself ~100-300 ms late.

The ATA runs a **line echo canceller (LEC)** that models the leak adaptively and subtracts it. It is
on by default ("Disable Line Echo Canceller: No"). If Grandma complains about echo, the fix is on
the ATA (Rx/Tx gain, or let the LEC retrain), not in Asterisk. The phone itself also has a tiny
hybrid for **sidetone** (you hear yourself in the receiver so the handset doesn't feel dead).

## 3. Dialing

### DTMF (what every cheap corded phone does)

Each key sends two sine waves at once for ≥40 ms. The ATA's DSP decodes them.

| Hz    | 1209 | 1336 | 1477 | 1633 |
|-------|------|------|------|------|
| **697** | 1 | 2 | 3 | A |
| **770** | 4 | 5 | 6 | B |
| **852** | 7 | 8 | 9 | C |
| **941** | * | 0 | # | D |

Once decoded, the digit either goes into the dialed number (pre-call) or, during a call, is
re-sent to Asterisk as an **RFC 2833/4733 telephone-event** RTP packet rather than as audio, so it
survives compression and so Asterisk can emit `ChannelDtmfReceived` to the backend. Set the ATA's
"Preferred DTMF" to RFC2833 first and Asterisk's endpoint to `dtmf_mode=rfc4733`.

### Pulse (rotary / thrift-store phones)

A rotary dial opens the loop N times at **10 pulses per second** (60 ms break / 40 ms make) for digit
N (0 = 10 pulses), with an inter-digit pause ≥ ~300 ms. Those breaks look like micro-hangups, so
the SLIC firmware has to recognise the pattern. **The HT801 V2 does support this**: "Enable Pulse
Dialing" under FXS Port → Analog Signal Line Configuration (default No), plus a "Pulse Dialing
Standard" selector. Verified in the HT80x V2 Administration Guide (Grandstream, Oct 2026 PDF);
the V1 guide lists dial methods "DTMF, Pulse" too. A rotary phone cannot send `*` or `#` and
has no way to send DTMF during a call, which is fine for us.

### How the ATA decides the number is complete

The ATA collects digits against its **Dial Plan** and sends `INVITE` when a rule matches. Grammar
(from the admin guide): `x` = one digit, `xx` = exactly two, `x+` = one or more, `|` = or, `T` =
wait 3 s more. Default is `{ x+ | +x+ | *x+ | *xx*x+ }`, which waits "No Key Entry Timeout" (4 s)
after the last digit. We want a single key to fire immediately, so the dial plan is **`{x}`**
(exactly one digit, no timeout). `INVITE sip:7@<pi>` leaves the ATA within milliseconds of the key.

Alternative for a keypad-less phone or a "pick up and it calls Mom" mode: **Off-hook Auto Dial**
(FXS Port → Call Settings) dials a fixed extension as soon as the handset lifts, after "Offhook
Auto-Dial Delay" seconds (0-60). The backend can map that extension (say `0`) to "menu" or to a
contact. Note the trade-off: with hotline on, the toddler never hears dial tone and can't choose.

## 4. Sampling and coding (inside the ATA)

- The hybrid's 4-wire receive side is band-limited to 300-3400 Hz and sampled at **8 kHz**, 16-bit.
- **G.711 µ-law (PCMU)** compands each sample to 8 bits: **64 kbit/s**, no compression delay,
  what the PSTN itself uses, so transcoding to the trunk is free. Pick PCMU first on the ATA and
  `allow=ulaw` on both Asterisk endpoints; everything stays in one codec end to end.
- Samples are packed **20 ms per RTP packet** (160 samples, 160 bytes + 12-byte RTP + 8 UDP +
  20 IP = 200 bytes, 50 packets/s each direction, ~80 kbit/s on the wire). The HT801 "Voice Frames
  per TX = 2" means 2 × 10 ms frames = 20 ms. Leave it.
- Silence suppression/VAD off (default): comfort noise makes a toddler think the line died.

## 5. SIP and RTP between ATA and Pi

Both on the LAN, no NAT, so this is the boring part.

1. ATA registers: `REGISTER sip:<pi>` as user `phone` with digest auth. Asterisk stores the
   contact (`pjsip show contacts`) and pings it with `OPTIONS` every `qualify_frequency` seconds.
2. Toddler presses 7: `INVITE sip:7@<pi>` with an SDP offer (PCMU, telephone-event, ATA's RTP port).
3. Asterisk answers `200 OK` with its own RTP port; from then on two UDP streams flow directly
   between ATA and Pi. `direct_media=no` on the endpoint keeps RTP anchored in Asterisk, which is
   what lets us record it.
4. Hangup from either side is a `BYE`.

Inbound (Asterisk ringing the phone) is the same with roles swapped: Asterisk sends `INVITE
sip:phone@<ata-ip>`, the ATA applies ring voltage until the loop closes, then sends `200 OK`.

## 6. What Asterisk does with the two legs

Every call enters the dialplan and immediately runs `Stasis(tincan, …)`, which parks the channel
in the backend's ARI application. The backend then:

1. **Plays prompts** on the single channel (`POST /channels/{id}/play` with `sound:` or a Piper
   WAV at 8 kHz mono). Audio is injected into the channel's read side; nothing else is involved.
2. **Originates the second leg** (`POST /channels` with `endpoint=PJSIP/+1555…@trunk`, or
   `PJSIP/phone` for inbound) into the same Stasis app.
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
| Phone → ATA analog | ~0 | wire |
| ATA packetization | 20 ms | one frame must fill before it can be sent |
| ATA → Pi LAN | <1 ms | |
| Asterisk jitter buffer + mixing | 20-60 ms | adaptive jitter buffer on the trunk leg; LAN leg needs none |
| Pi → provider | 10-40 ms | depends on which POP you pick; choose the nearest |
| Provider → PSTN → cell network | 100-250 ms | mobile networks add the most; nothing we can do |
| Far-end phone jitter buffer + decode | 20-80 ms | |
| **Total one way** | **~170-450 ms** | ITU G.114 says <150 ms is unnoticed, <400 ms acceptable. Grandma-to-toddler feels like a normal cell call. |

Wi-Fi on either the Pi or the ATA adds jitter, not latency, and jitter is what makes words drop.
Both are wired for a reason.

## 9. ATA configuration that matters (summary; procedure in hardware/ata-setup.md)

| Goal | HT801 V2 setting | Value |
|------|------------------|-------|
| One key = one call, instantly | FXS Port → Call Settings → **Dial Plan** | `{x}` |
| or: lift handset = call | FXS Port → Call Settings → **Off-hook Auto Dial** | an extension, e.g. `0` |
| Toddler can't trigger PBX features | **Enable Hook Flash** No, **Disable Call-Waiting** Yes, star codes off | |
| One codec end to end | FXS Port → Codec Settings → **Vocoder Settings** | PCMU first, PCMA second |
| Digits as events | **Preferred DTMF** | RFC2833 first |
| Rotary phone | FXS Port → Analog Signal Line Configuration → **Enable Pulse Dialing** | Yes |
| Louder ring for a big bell | **Ring Power** | 55Vrms |
| Register to the Pi | FXS Port → General Settings → **Primary SIP Server** / **SIP User ID** / **Authenticate Password** | `<pi-ip>`, `phone`, `$PHONE_SIP_PASSWORD` |

## 10. How the phone rings on demand

Nothing on the ATA is "a ring command". The backend asks Asterisk to **originate** a call to the
ATA (`POST /channels?endpoint=PJSIP/phone&app=tincan&appArgs=inbound,…`). Asterisk sends an
`INVITE` to the ATA's registered contact; the ATA answers `180 Ringing` and applies ring voltage in
its configured cadence (default North American 2 s/4 s; "System Ring Cadence" under Advanced
Settings; alternate cadences can be selected per call with a SIP `Alert-Info` header, which
`PJSIP_HEADER(add,Alert-Info,…)` can set if you ever want a special "Grandma ring"). When the
toddler lifts the handset the ATA sends `200 OK`, the channel enters Stasis, and the backend
bridges it to the waiting trunk leg. If nobody answers, the backend cancels the originate after
`ring_timeout_seconds` and the ATA stops ringing on the `CANCEL`. The "test call" button in the
parent UI is literally this with a prompt instead of a trunk leg.
