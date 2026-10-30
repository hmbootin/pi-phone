# v2: DIY analog line interface (SLIC module + Pico 2 W + USB sound card)

The tinker path from [ADR 0002](../docs/adr/0002-ata-not-diy-line-interface.md). It replaces the
$35 HT801 with ~$25 of parts and a few weekends. Nothing in v1 depends on it. Build it when the
toddler already has a working phone and you want to understand what the ATA was doing.

**Honest difficulty:** hook and dial sensing is an afternoon (the Pico code already does it). Ring
is an evening. Clean, echo-free, hum-free audio into Asterisk at the right level is the part that
takes weeks, and the part the HT801 does with a $2 DSP. Expect to buy a scope or at least a
second USB sound card to look at the waveforms.

## What a SLIC module gives you

A ringing SLIC module is a 1 × 2 cm board with a DC/DC converter that makes the -48 V battery and
the ~75 V ring supply from 3.3-5 V, a constant-current loop feed, a hybrid (2-wire ⇄ 4-wire), and
three logic pins. The two you can buy:

| Module | Pins (SIL) | Supply | Loop current | Ring | Price | Source |
|--------|-----------|--------|--------------|------|-------|--------|
| **Silvertel Ag1171** | 14-pin, 2.54 mm | 3.3-5.0 V | preset ~25 mA | ~60 Vrms into 1 phone, 72 V battery during ring, 20-25 Hz, up to 3 tone ringers | **$8.50** single unit; 16-week lead, backordered to 2027 at Newark | [DigiKey](https://www.digikey.com/en/products/detail/silvertel/AG1171/21187236), [datasheet v1.6](https://static.chipdip.ru/lib/300/DOC029300244.pdf) |
| Silvertel Ag1170 | 14-pin SIL or 21-pin DIL | same | longer loops (3 km / 800 Ω) | same scheme | ~$10-12 | [Mouser datasheet](https://www.mouser.com/catalog/specsheets/Silvertel_Ag1170v1_15.pdf) |
| **KS0835F "SLIC module"** (Ring&Tone, Shenzhen) | 11-pin, 2.54 mm; pin-compatible in spirit with the Ag1171 | 3.2-5.5 V | 23-31 mA | 130 Vpp (~46 Vrms), 75 V battery; 3 tone ringers or 2 mechanical bells | ~$8-15 as "KS0835F SLIC module" on AliExpress/eBay/Amazon (price not verified this week; sold as the Arduino "phone ringer" module) | [datasheet](https://wiki.wut.ee/project/pots/1130655_113518007.pdf), [GadgetReboot breakout](https://github.com/GadgetReboot/KS0835F_Phone_SLIC) |

The Ag1171 is the documented, in-stock-at-a-real-distributor part. The KS0835F is cheaper and is
what every Arduino/ESP32 rotary-phone project on GitHub uses, so there is more sample code. Buy
whichever you can get this month; the pin functions are the same.

## Pinout (both modules)

| Function | Ag1171 pin | KS0835F pin | Direction | Notes |
|----------|-----------|-------------|-----------|-------|
| RING (B) | 1 | 1 | line | to the phone's RJ11 (centre pair, pins 3-4) |
| TIP (A) | 2 | 2 | line | |
| **F/R** Forward/Reverse | 3 | 3 | in | Ag1171: *low* reverses polarity. KS0835F: *high* reverses. Toggle at 20 Hz to ring. |
| **RM** Ring Mode | 4 | 4 | in | High only while ringing (raises battery to 72-75 V). |
| **SHK** Switch Hook | 5 | 5 | out | High = off-hook (loop current flowing). Bounces; debounce 10 ms+. Pulses during ring trip. |
| Audio in (to line) | 9 `VIN` via 10 nF | 6 `VR` | in | from the sound card's headphone/line out |
| Audio out (from line) | 10 `VOUT` via 100 nF | 7 `VX` | out | to the sound card's mic/line in |
| GND (DC/DC) | 12 | 9 | | |
| +V (3.3 or 5 V) | 13 | 10 | | draws 270-320 mA off-hook and during ring: **power from the Pi's 5 V or a separate supply, not the Pico's 3V3 regulator** |
| PD Power Down | 14 | 11 | in | leave floating or pull low to sleep. **Never drive high.** |
| NC | 6, 7, 8, 11 | 8 | | |

Logic pins are 3.3 V tolerant on both; SHK is driven by the module, read it with a plain input
(no pull-up needed; RetroPhone notes SHK bounces more at 3.3 V than 5 V).

## Wiring to the Pico 2 W and the Pi

```
                      ┌──────────────┐        ┌──────────────────────────┐
  phone ──RJ11──┐     │  SLIC module │        │ Pico 2 W (MicroPython)   │
   tip ─────────┼─────┤2 TIP         │        │                          │
   ring ────────┼─────┤1 RING   F/R 3├────────┤GP16  out                 │
                      │         RM  4├────────┤GP17  out                 │
                      │         SHK 5├────────┤GP15  in   (= "hook")     │
                      │      audio in├──10nF──┼─────────────── headphone out ┐   ┌──────────────┐
                      │     audio out├──100nF─┼─────────────── mic in        ├───┤ USB sound    │
                      │     +5V   GND│        │GND ─────────────────────────┘   │ card on Pi   │
                      └───┬───────┬──┘        └──────────────────────────┘      └──────┬───────┘
                       Pi 5V    GND  (common ground with Pico and sound card)         USB → Pi
```

- The Pico does signalling (hook, pulses, ring cadence) and reports over Wi-Fi or USB serial to
  the backend. The Pi does audio through a $10 USB sound card (any CM108/CM119-based dongle,
  e.g. Sabrent AU-MMSA or UGREEN; ~$8-13). The Pico 2 W has no ADC fast enough and no DAC for
  real-time full-duplex audio; don't try.
- Audio levels: the SLIC's 4-wire side is roughly 0 dBm into 600 Ω (~0.77 V RMS). A headphone
  output at 1/3 volume is about right into `VIN`; `VOUT` into a mic input needs the input gain near
  minimum or a 10:1 divider. Use `alsamixer` on the Pi. Get it wrong and you get either clipping
  or a floor of hum.
- Ground loops are the hum source: single ground point at the Pi, short leads, twist tip/ring.
- Keep the phone pair away from the Pi's power cable; 20 Hz ringing couples into everything.

## Firmware on the Pico (what exists, what to add)

Existing code in `firmware/pico/src/` already does the hook/dial half for a keypad wired directly
to GPIOs: `inputs.py` is a debounced active-low switch reader (20 ms) and `main.py` prints
`hook down/up` and digit events. (`pinmap.py` maps `"0"` to GP14 while `hardware.md`'s table says
GP11/pin 15; the code is the source of truth, fix the doc when you touch it.)

For a SLIC the inputs change: there is one signal, SHK, and digits come from it.

1. **Hook**: SHK high = off-hook. Reuse `Input` with `active_high=True` (one-line change) and a
   longer debounce (RetroPhone and the Ag1171 datasheet both say ≥10 ms; use 20).
2. **Pulse dialing**: while off-hook, each dial pulse is a 60 ms SHK low. Count lows separated by
   <100 ms into one digit; a gap >300 ms ends the digit (10 pulses = `0`). A gap >1000 ms low is a
   hangup, not a pulse. Stop any dial tone on the first falling edge, before debounce, or the
   tone "blips".
3. **DTMF**: not from SHK; it's audio. Either decode on the Pi from the sound card stream
   (Goertzel on 8 kHz samples, ~40 lines of Python, or let Asterisk do it with `dtmf_mode=inband`)
   or add an **MT8870 decoder module** ($3) between `VOUT` and four Pico GPIOs + a strobe pin.
   RetroPhone tried software decoding on the ESP32 and gave up in favour of the MT8870.
4. **Ring**: `RM=1`; then toggle `F/R` every 25 ms (20 Hz) for 2 s; `F/R` back to the forward
   level; wait >10 ms; `RM=0`; pause 4 s; repeat. Poll SHK every 5 ms during ringing: on the
   first debounced high, stop toggling, drop RM within 500 ms (datasheet hard limit, it's
   dissipating power into an off-hook load), and report "answered". The Pico's second core or a
   PIO state machine is the clean place for the 20 Hz toggle.
5. **Dial tone / busy / prompts**: not the Pico's job; Asterisk plays them into the sound card once
   the Pi's SIP user agent has an active call. Between off-hook and the first digit you therefore
   need the Pi to open a call immediately (auto-answer into a Stasis app that plays dial tone with
   `tonezone`), or accept ~1 s of silence before a prompt.
6. **Transport to the backend**: the existing plan for M4 extra buttons (HTTP POST or MQTT over
   Wi-Fi) works unchanged: events `{"hook":"off"}`, `{"digit":"7","method":"pulse"}`,
   `{"ring":"answered"}`; commands `ring start/stop`.

## Getting the audio into Asterisk

The sound card is an ALSA device on the Pi. Three ways to make it a channel Asterisk can bridge
and record:

| Option | How | Verdict |
|--------|-----|---------|
| `chan_alsa` (Asterisk's own console channel) | `Dial(Console/dsp)`; `alsa.conf` points at `plughw:1,0`. | Deprecated in Asterisk 19, still present in 20, **removed in 21**. Single channel, flaky on Pi (sample-rate drift, choppy audio reports). Only for a first proof of life. |
| **baresip** as a SIP phone on the Pi | `baresip` with the `alsa` module, registers to Asterisk as endpoint `phone`, `auto_answer`, controlled over its TCP/HTTP ctrl interface by the backend (answer, dial `sip:7@localhost`, hangup). | **Recommended.** Packaged on Raspberry Pi OS (`apt install baresip baresip-core`), runs in its own container, Asterisk sees an ordinary SIP endpoint so nothing else in the stack changes. |
| `pjsua` (pjsip's CLI) | Same idea, `--playback-dev/--capture-dev`, `--auto-answer 200`. | Works, less maintained CLI, harder to script. |
| Bare RTP with the Pi's `ExternalMedia` ARI channel | ARI `POST /channels/externalMedia` hands you an RTP socket; a 60-line Python loop pumps PCM between ALSA and that socket. | Fun, fully in our control, and you own jitter and clocking. Do it third. |

With baresip the Pico's "off-hook" event makes the backend tell baresip to place a call to
`sip:dialtone@asterisk` (a Stasis app that plays dial tone and collects DTMF/pulse digits the
backend forwards as `POST /channels/{id}/dtmf`); everything after that is identical to v1. The ATA
is now a Pico, a $10 module and a $10 dongle.

## Echo and levels, the part that eats the weekends

The HT801 has a line echo canceller; your SLIC does not. Asterisk has none either (there is no
software echo canceller for non-DAHDI channels). So the far end hears their own voice back from the
SLIC's hybrid mismatch, delayed by the Pi's audio buffers (50-150 ms), which is the worst case.
Mitigations in order of effort: match the line impedance (both modules are 600 Ω; a modern phone
is a "complex" impedance and will mismatch a bit), keep the ALSA period small (`period_size=160`),
lower `VIN` level so less leaks, and finally run the stream through SpeexDSP's AEC in the
Python ExternalMedia loop (`speexdsp` has Python bindings; it works at 8 kHz).

## Safety

Ring voltage is 75-130 Vpp. It stings and it will destroy a GPIO. Never let tip/ring touch the
logic side, keep the module off the breadboard rails once ringing works, and don't ring while
holding the bare pair. The modules' current limit makes them survivable but not pleasant.

## Shopping list

| Item | Price |
|------|-------|
| Ag1171 (DigiKey) or KS0835F module | $8.50 / ~$10 |
| USB sound card (CM108-class) | ~$10 |
| MT8870 DTMF module (optional) | ~$3 |
| 10 nF + 100 nF caps, RJ11 breakout or jack, hookup wire | ~$5 |
| Pico 2 W | owned |
| **Total** | **~$25-30** |
