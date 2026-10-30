# Phone interface: wiring the LD-858 phone into the Pi

How the sourced landline phone's keypad, hook switch, handset and speaker connect to the Raspberry
Pi. The phone's own line-side electronics are bypassed: there is no phone line, no ATA and no SLIC
anywhere in the build (see [ADR 0002](../docs/adr/0002-direct-phone-interface.md)). Short version
for non-electrical readers: [phone-interface-overview.md](phone-interface-overview.md).

Status: **pending measurements** (section 3). Written 2026-10-30 from photos of the main PCB
(front and back), the two keypad PCBs, and the handset interior.

## 1. What is on the board

Main board: `LD-858SOSBMB`, dated 2024-09-27. Keypad boards: `LD-858SOSKB1` (memory keys M1-M9 and
SOS, plus the base speaker and LED pads) and `LD-858SOSBKB2` (0-9, `*`, `#`, STORE, SPEAKER, REDIAL,
FLASH, and a "USE" LED spot). The "SOS" in the part numbers is the big SOS key: this is an
amplified "big button" phone with memory dialing and a **speakerphone** (`U3` is an `MC34018P`
voice-switched speakerphone IC, and the keypad has a SPEAKER key). It has a `MED/HI/VHI` handset
volume switch and a `HI/LO/OFF` ringer switch. No DC input: the whole thing runs on loop current
from the RJ11 jack. Once we stop plugging a line in, every chip is dead, which is what we want.

Wiring seen in the photos:

- Line jack (grey RJ11, top centre) → red/green wires → pads by `Z3`/`QD1`. The line.
- Handset modular jack (top right corner) → yellow/black/red/green bundle → pads around `R51`/`Q7`
  (yellow) and `C22`/`D12` (red, black, green). The back silkscreen calls these `SP+`, `SP-`,
  `HM+`, `HM-`.
- Inside the handset: a round receiver capsule on the left (yellow/black wires), a small cylindrical
  electret mic capsule on the right (red/green wires), a steel counterweight in the middle, and the
  4-contact modular jack. Exactly the mic + receiver pair we want.
- Keypad: KB2 (dial keys) chains into KB1 (memory keys) by one heat-sealed flex, and KB1 chains into
  the main board by a second flex that lands on the row of ~20 tinned pads next to `R78`. The flex at
  the KB1 end is labelled roughly `SPK-, SPK+, LED+, KL+, K/O, R1, R2, C5, C4, C3, C2, C1, R3, …, H5,
  VSS`, so the ribbon carries at least 3 rows and 5 columns, plus the base speaker and an LED.
- Base speaker (two black wires on KB1's `SPK+`/`SPK-` pads, mounted in the keypad deck). This is
  the speakerphone's loudspeaker. **We reuse it as the ringer**, so no speaker purchase.
- Lone red wire at bottom right (`R21`/`Q10`) → the base microphone for the speakerphone. Not needed.
- `B+`/`B-` (back, by `HI/LO/OFF`) → piezo ringer disc. Spare.

Identified components:

| Ref | Part | Function | Fate |
|---|---|---|---|
| RJ11 jack (grey, top centre) | line jack, red/green = tip/ring | line input | **discard** (unplug forever; its hole becomes the cable exit) |
| `VR1` (axial, between pads marked `R` and `T`) | varistor across the line | surge protection | discard (inert) |
| `QD1`, `QD2` (`MB6F`) | SMD bridge rectifiers | line polarity guards (speech and ringer paths) | discard (inert) |
| `U4` `KA2411` + `Z1`, `D1`, `C7`, `R3` | tone ringer IC | drives the piezo from ring voltage | discard; piezo stays as a spare |
| `B+`/`B-` pads | piezo ringer | ringer | spare; the base speaker replaces it |
| `U3` `MC34018P` + `U6`, the right half of the board | speakerphone IC and its amp/mic circuitry | hands-free mode | discard (inert) |
| Base speaker (black wires to KB1 `SPK+`/`SPK-`) | speakerphone loudspeaker, probably 8-50 Ω | | **reuse as the ringer** on the PAM8403 (measure ohms first) |
| Base mic (lone red wire, bottom right) | speakerphone electret | | discard, or keep as a spare mic |
| Keypad LED (`LED+` on the flex, "USE" spot on KB2) | in-use indicator | | **reuse** from a GPIO through 330 Ω (optional) |
| `HI/LO/OFF` slide switch | ringer volume | | **reuse** as a 2-GPIO ringer volume selector (optional) |
| `MED/HI/VHI` slide switch | handset amplification | | reuse as GPIO or ignore |
| `U9` (SSOP-20) + `X1` (3.58 MHz crystal) | DTMF dialer / keypad controller | scans the keypad, generates tones | **remove U9** so its pins stop loading the key lines |
| Keypad flex ribbon (left edge, ~20 tinned pads next to `R78`) | heat-sealed connection to KB1, which chains to KB2 | 26 keys as a matrix of roughly 5-6 rows x 5 columns | **reuse**: solder our wires to those pads; the two keypad PCBs and both flexes stay untouched |
| Right-hand analogue section (`Q5/Q6/Q14/Q18`, `C19/C20`, `J6`, electrolytics `E1..E25`) | speech network / hybrid / handset amp | 2-wire to 4-wire, sidetone, amplification | discard (inert) |
| `SP+`/`SP-`, `HM+`/`HM-` pads (bottom right, yellow/black/red wires) | handset receiver (SP) and handset mic (HM) | | **reuse**: desolder the four handset wires and run them to the USB sound card |
| `HK` (blue block with white actuator, right edge) | hook switch | off-hook detect | **reuse**: GPIO input |
| `VDD`, `GND`, `NC1`, `NC2`, `COL2`, `COL4` test points (back, by the ribbon) | dialer supply and keypad columns | | handy probe points for the keypad mapping |

Rule of thumb: the only things worth keeping are the ones that are **mechanical or transducers**
(keys, switch, mic, receiver, speaker, enclosure, cord). Every semiconductor on the board exists to
live on a 48 V line, and there is no line.

Why not keep the dialer IC and read its tones? Because decoding DTMF from the audio path means the
keypad only works off-hook, the Pi needs an extra audio input, and we would still need a 2-wire
hybrid. Seven GPIO lines are simpler than any of that.

## 2. Target architecture

```
                         ┌──────────────── phone housing ────────────────┐
  handset cord (4 w)     │                                               │
 ┌─────────┐  HM+/HM-    │   ┌──────────────┐   mic (TRS)   ┌─────────┐  │
 │ electret├─────────────┼──▶│ 3.5 mm plug  │──────────────▶│ USB     │  │
 │ mic     │             │   └──────────────┘               │ audio   │──┼──USB──▶ Pi 4
 │ receiver│◀────────────┼───┤ 3.5 mm plug  │◀──────────────┤ adapter │  │
 └─────────┘  SP+/SP-    │   └──────────────┘  headphone L  └─────────┘  │
                         │                                               │
   keypad flex pads ─────┼── rows R1..R4 ──(1 kΩ each)──────────────────┼──▶ GPIO inputs (pull-up)
                         │── cols C1..C3 ──(1 kΩ each)──────────────────┼──▶ GPIO outputs (open-drain style)
   hook switch HK ───────┼── (1 kΩ) ─────────────────────────────────────┼──▶ GPIO input (pull-up)
   HI/LO/OFF switch ─────┼── 2 lines ────────────────────────────────────┼──▶ 2 GPIO inputs (optional)
                         │                                               │
   base speaker (reused)◀┼── PAM8403 amp ◀── 3.5 mm ◀─────────────────────┼──── Pi headphone jack
                         │        ▲ 5 V from Pi header                   │
                         └───────────────────────────────────────────────┘
```

- **Handset audio**: the handset mic and receiver go straight into a CM108-class USB audio adapter.
  Those adapters put 2-4.5 V of "plug-in power" on the mic tip through a few kΩ, which is exactly
  the bias an electret capsule wants. The headphone output drives a 100-300 Ω receiver with room to
  spare.
- **Keypad and hook**: 26 keys (0-9, `*`, `#`, STORE, SPEAKER, REDIAL, FLASH, M1-M9, SOS) as one
  switch matrix, about 11 lines, scanned by the Pi. Rows are inputs with the Pi's internal pull-ups;
  columns are driven low one at a time. 1 kΩ in series with every line protects the GPIO if two keys
  are pressed while a column is driven. The memory keys are a gift: M1 = Grandma, M2 = Dad, with no
  digit to remember, and SOS can be "call a parent".
- **Ringer**: the Pi 4's own headphone jack into a $2 PAM8403 class-D amplifier into the phone's
  existing base speaker (the speakerphone's loudspeaker, already mounted under the keypad deck).
  Ringtone is a WAV file. Keeping the ringer on the Pi's built-in jack rather than the USB card's
  second channel avoids any ALSA channel-splitting.
- **Power**: everything hangs off the Pi's 5 V. The PAM8403 draws <0.5 A at full blast; the USB card
  <0.1 A. Use the official 3 A supply.

Pi placement: the host is a Pi 4 (ADR 0001). Inside the base is nice but not required. Default
plan: the Pi sits next to the phone and a short bundle (USB cable to the audio adapter, 3.5 mm lead
to the amp, and a 40-pin ribbon or a dozen jumper wires) leaves through the old RJ11 hole. If the
cavity under the keypad deck clears 90 x 60 x 25 mm, move the Pi inside at stage 5.

## 3. Measurements to make before buying anything

You need a multimeter, the phone open, the line **unplugged**, and the handset cord unplugged from
the base. Record answers in section 9 of this file.

### 3.1 Keypad matrix map (the only hard one)

1. Number the tinned ribbon pads on the front of the PCB (the vertical row next to `R78`) from the
   top: P1, P2, … Count them. The back silkscreen (`NC1`, `NC2`, `COL2`, `COL4`) sits beside the
   same pads and tells you the pitch of the labels.
2. Set the meter to **ohms (not continuity beep)**. Carbon-pill keys read 50-500 Ω when pressed,
   which is often above the beep threshold.
3. With no key pressed, probe a few pad pairs; expect OL (open) or >10 kΩ (through `U9`). Anything
   under 1 kΩ with no key pressed is a pad tied to another on the PCB; note it.
4. Press and hold `1`. Walk one probe along the pads with the other fixed on P1, then P2, … until
   the reading drops from OL to under ~1 kΩ. That pair is `1`'s row and column. Faster: once you find
   the pair for `1`, the same row pad will serve `2` and `3`, and the same column pad serves `4`, `7`,
   `*`. Fill the table in section 9.
5. Repeat for every key, including any extras (redial, flash, mute, memory keys). Extras may be
   on their own pads or on a 4th column.
6. Count distinct pads used. Expect 10-12 for 26 keys (5-6 rows x 5 columns). The flex labels on
   KB1 (`R1 R2 R3`, `C1..C5`, `H5`, `K/O`, `KL+`) hint at the layout. Lines you can ignore: `SPK+`/
   `SPK-` (base speaker, we tap it separately), `LED+`, `VSS`. If some keys turn out to be a single
   line to `VSS` instead of a matrix position, they just become one GPIO each. The Pi has 26 usable
   GPIOs; an MCP23017 I/O expander is the fallback if it ever gets tight.
7. While you are there: ohms across the two black wires on KB1's `SPK+`/`SPK-` pads (the base
   speaker). 4-50 Ω means a real speaker and it becomes the ringer; OL means piezo, buy the speaker in
   the BOM instead.

If the readings are confusing because `U9` is in circuit, lift `U9` first (section 5, step 2) and
redo the map; with the IC gone every pad is purely passive.

### 3.2 Hook switch

1. Find the terminals of the blue `HK` block on the back (2 or 3 pins, maybe 6 if DPDT).
2. Ohms between each pair with the actuator released (handset lifted) and pressed (handset down).
3. You want one pair that reads ~0 Ω in one state and OL in the other. Note which state is closed.
   Either polarity works in software; we just need to know it.

### 3.3 Handset: what kind of mic and receiver

Probe the 4 contacts of the handset cord's modular plug (handset end still attached). Contacts
are usually paired as the outer two (one transducer) and the inner two (the other).

| Reading | Meaning |
|---|---|
| 50-350 Ω either polarity | dynamic receiver (expected on `SP+/SP-`). Good: headphone out drives it directly. |
| OL one way, 0.5-2 V in diode mode or a few kΩ the other way | electret mic with built-in FET (expected on `HM+/HM-`). Good: USB card bias works. |
| OL both ways on both pairs | piezo receiver, or a mic with no FET. Tell me; it changes the mic wiring. |
| ~0 Ω on a pair | shorted or a shared common. Tell me. |

Also note the colour of each wire at `SP+`, `SP-`, `HM+`, `HM-` on the PCB and which plug contact it
reaches (ohms from pad to plug contact).

### 3.4 Ringer piezo (just to decide its fate)

Ohms across `B+`/`B-`: OL means a bare piezo disc (useless at 3.3 V; keep as spare). Not needed if
the base speaker in 3.1 step 7 reads as a speaker.

### 3.5 Fit

Internal clear height and footprint of the base cavity under the keypad deck, and whether the Pi's
Ethernet/USB-C can reach the RJ11 hole.

## 4. Bill of materials (interface parts only; Pi and storage are in [bom.md](bom.md))

Path of least resistance: screw terminals and plugs wherever a connector exists, solder only where
the phone leaves no choice (the keypad pads, the hook switch, freeing wires from the main board).

| # | Item | Qty | ~Cost | Notes |
|---|---|---|---|---|
| 1 | USB audio adapter with **separate** pink mic and green headphone jacks, CM108/CM119 based (Sabrent AU-MMSA, UGREEN 30724, or similar) | 1 | $8-12 | Not the single-jack TRRS "headset" type. |
| 2 | 3.5 mm male TRS **screw-terminal** plugs | pack of 5 | $6 | Two for the handset (mic, earpiece), spares for the amp. |
| 3 | PAM8403 amplifier module **with a 3.5 mm input socket** and screw-terminal speaker/power outputs ("PAM8403 3.5mm" on Amazon/AliExpress) | 1 | $3-7 | The bare-pad variant works but needs soldering. |
| 4 | 3.5 mm male-to-male aux cable | 1 | $0 | Scavenge from old headphones or any aux lead. Pi headphone jack to amp input. |
| 5 | Female-to-male jumper wires | 1 pack | $5 | Keypad pads and hook switch to the breadboard, amp 5 V and ground from the Pi header. |
| 6 | 1 kΩ resistors, 1/4 W | 15 | $3 or have | One per GPIO line. |
| 7 | 40-pin GPIO ribbon + breadboard breakout (T-cobbler) | 1 | $7-10 | Breadboard phase; a proto HAT (~$8) for the final build. |
| 8 | Solder wick or desoldering pump | 1 | $5 | Freeing the handset wires and removing `U9`. |
| 9 | Breadboard, hookup wire, heat shrink, hot glue, zip ties | – | have | Strain relief on every wire that leaves the PCB. |

Core total: about **$30-40**. Tools assumed: multimeter, soldering iron, flush cutters, hobby knife,
small Phillips driver.

Buy only if a measurement says so:

| Item | ~Cost | Trigger |
|---|---|---|
| Small speaker, 8 Ω, 1 W, 28-40 mm | $3-5 | base speaker reads open across `SPK+`/`SPK-` (3.1 step 7) |
| MCP23017 I2C GPIO expander breakout | $3-5 | keypad map needs more than ~15 lines |
| 330 Ω resistor | – | only if you wire the keypad's "USE" LED |

## 5. Schematics

### 5.1 Keypad and hook switch to GPIO (6 rows x 5 columns budgeted; use what the map needs)

```
                        Pi 40-pin header (BCM numbering)
 keypad pad  1k
   ROW1 ────/\/\/──────── GPIO5   (input, pull-up)
   ROW2 ────/\/\/──────── GPIO6   (input, pull-up)
   ROW3 ────/\/\/──────── GPIO13  (input, pull-up)
   ROW4 ────/\/\/──────── GPIO19  (input, pull-up)
   ROW5 ────/\/\/──────── GPIO25  (input, pull-up)
   ROW6 ────/\/\/──────── GPIO8   (input, pull-up)
   COL1 ────/\/\/──────── GPIO12  (output, scanned low)
   COL2 ────/\/\/──────── GPIO16  (output, scanned low)
   COL3 ────/\/\/──────── GPIO20  (output, scanned low)
   COL4 ────/\/\/──────── GPIO21  (output, scanned low)
   COL5 ────/\/\/──────── GPIO7   (output, scanned low)

   HK common ───/\/\/──── GPIO26  (input, pull-up)
   HK contact ──────────── GND

   HI/LO/OFF  centre ───── GND
              "HI" ──1k── GPIO23 (pull-up)      optional
              "LO" ──1k── GPIO24 (pull-up)      optional
```

Scanning: drive one column low, read the four rows, release the column (set it as input), next
column, 100 Hz, debounce 20 ms. With only one column driven at a time and 1 kΩ in every line, a
toddler mashing three keys at once can never short an output high to an output low.

If any extra key is a single line to a common pad, treat it like the hook switch: one GPIO with
pull-up, common to GND.

### 5.2 Handset to USB audio adapter

```
 handset mic   HM+ ───────────────── TIP   ┐ 3.5 mm TRS into the adapter's MIC jack
 (electret)    HM- ───────────────── SLEEVE┘ (ring unconnected, or tie to tip on CM108 cards
                                               that bias the ring instead; measure which contact
                                               carries 2-4.5 V DC with nothing plugged in)

 handset rcvr  SP+ ───/\/\/ 100 Ω ── TIP   ┐ 3.5 mm TRS into the adapter's HEADPHONE jack
 (dynamic)     SP- ───────────────── SLEEVE┘ (ring = right channel, leave unconnected)
```

With screw-terminal plugs: strip the handset wire, screw it into the terminal marked T (tip) or
S (sleeve), leave R empty. The 100 Ω resistor can be skipped if software volume stays under ~70 %.

The electret capsule is polarised: `HM+` is the terminal that was fed bias on the original board
(it is the one with a resistor path to `VDD`; confirm with ohms to the `VDD` test point). If you
get it backwards the mic is just silent, nothing breaks; swap the wires.

### 5.3 Ringer

```
 Pi headphone jack  TIP (L) ──────── PAM8403 L_IN
                    SLEEVE ─────────  PAM8403 GND
 Pi header pin 2 (5 V) ──────────── PAM8403 VCC   (+ 10 µF and 100 nF across VCC/GND at the module)
 Pi header pin 6 (GND) ──────────── PAM8403 GND
 PAM8403 L_OUT+ / L_OUT- ──────────── base speaker (unsolder its two black wires from KB1's SPK+/SPK-)
```

Leave the PAM8403's right channel unconnected. If the module has a volume pot, set it once at about
a third and do the rest in software. Never bridge the amp outputs to ground; they are bridge-tied.

### 5.4 Optional: the keypad's "USE" LED as an in-call light

```
 GPIO17 ──/\/\/ 330 Ω ──── LED+ pad on the flex      (LED cathode is on VSS; tie VSS to Pi GND)
```

## 6. Assembly and test plan, in stages

Each stage ends with a test you can run before touching the next stage. Do not cut anything in
stage 0.

### Stage 0: survey (no changes)

- Do every measurement in section 3 and fill in section 9.
- Photograph the board front and back again (the earlier front/right/keypad/handset photos did not
  arrive) and keep the images in `docs/images/phone/`.
- Verify: you can explain every key as a (row, col) pair, you know which HK state is "off hook",
  and the handset reads as electret + dynamic.

### Stage 1: handset audio on the bench

1. Desolder the four handset wires from `SP+`, `SP-`, `HM+`, `HM-` (or cut the wires an inch from the
   pad and strip them; the pads are not needed again).
2. Screw them into two 3.5 mm screw-terminal plugs per 5.2 (tip and sleeve), optional 100 Ω in
   the receiver lead.
3. Plug both into the USB adapter, adapter into the Pi. `arecord -l` and `aplay -l` should list it.
4. Test:

   ```
   arecord -D plughw:1,0 -f S16_LE -r 8000 -c 1 -d 5 /tmp/mic.wav
   aplay -D plughw:1,0 /tmp/mic.wav
   ```

   Speak into the handset, then hold it to your ear. Use `alsamixer -c 1` to set capture gain to
   ~70 % and enable "Auto Gain Control" if present; set playback to ~50 %.
5. Pass criteria: speech is intelligible both ways, no hum (a hum means a ground loop between the
   PAM8403 5 V and the USB card; it goes away once the amp is on the same Pi), DC on the mic tip
   measures 2-4.5 V.

### Stage 2: hook switch and keypad on the breadboard

1. Remove `U9` so the key lines are passive: cut its 20 legs at the body with a hobby knife or
   fine flush cutters, then wick the stubs off the pads. (Hot air works too; nothing nearby matters.)
   Leave `X1` and everything else; they are inert without `U9`.
2. Solder a wire to each keypad pad you mapped in 3.1 (solder onto the existing tinned pad from
   the front; a dab of flux, 2 seconds, done). Colour-code rows vs columns. Hot-glue the bundle to the
   PCB as strain relief.
3. Solder two wires to the `HK` switch pair you found in 3.2.
4. Breadboard per 5.1 with the T-cobbler and 1 kΩ resistors. Connect to the Pi powered off, then boot.
5. Test with a throwaway scanner (will live at `backend/tincan/hardware/keypad.py`, but a 30-line
   `gpiozero` script is fine first):

   ```
   # prints "1", "2", ... on press and "offhook"/"onhook" on the cradle
   uv run python scripts/keyscan.py
   ```

6. Pass criteria: every key prints exactly once per press with no repeats or neighbours; pressing
   two keys in the same row prints both and nothing else (no ghosting); lifting and replacing the
   handset toggles the hook state within 50 ms and does not chatter.

### Stage 3: ringer

1. Unsolder the base speaker's two black wires from KB1's `SPK+`/`SPK-` pads, extend them if
   needed, and screw them into the PAM8403's left speaker terminals. The speaker stays where it is.
2. Aux cable from the Pi's headphone jack into the amp's 3.5 mm socket; 5 V and ground from the Pi
   header (pins 2 and 6) into the amp's power terminals with two jumper wires.
3. Set the Pi's audio output to the headphone jack (`raspi-config` → Audio, or `amixer cset numid=3 1`).
4. Test with `aplay /usr/share/sounds/alsa/Front_Center.wav`, then a real ringtone WAV.
5. Pass criteria: loud enough to hear from the next room with the `HI/LO/OFF` switch (if wired)
   changing the software volume, no buzz when idle (if there is idle hiss, add the 10 µF/100 nF at
   the amp and route the audio lead away from the 5 V lead).

### Stage 4: software integration

- The `phone` Compose service (`baresip`, ALSA audio, `ctrl_tcp` control module) registers to
  Asterisk as the PJSIP endpoint `phone`. Audio device = the USB adapter. Asterisk config stays static.
- Backend gets a `hardware` service: keypad + hook scanner (gpiozero), ringer player (aplay to the
  Pi jack), and a baresip client. Hook off → tell baresip to dial the pressed digit at Asterisk;
  incoming INVITE on baresip → start ringtone; hook off while ringing → answer; hook on → hangup.
- All the ARI/policy/recording code is untouched: Asterisk still sees a SIP phone called `phone`.
- Fake the GPIO and baresip in tests the same way `fake_ari.py` fakes Asterisk.

### Stage 5: final build

1. Move the breadboard circuit to a proto HAT or a scrap of perfboard: 8-10 resistors and a header.
2. Mount the Pi in the base; Ethernet + USB-C out through the RJ11 hole, with a grommet or hot glue.
3. Strain-relieve every cable to the housing, not to the PCB.
4. Reassemble; 24 h soak test with the toddler-mashing script (random key presses + hook toggles).

### Stage 6: safety checks (CLAUDE.md rule: anything the toddler triggers must fail safe)

- Pull the USB audio adapter mid-call: backend must detect the device disappearing, hang up, and
  play nothing rather than leave an open line.
- Pull the handset cord: receiver open-circuit is harmless to the headphone output; mic open just
  goes silent.
- Pi reboot with the handset off-hook: on boot the scanner reads off-hook and must not auto-dial.
- No voltage anywhere in the phone exceeds 5 V, so the toddler-accessible parts need no isolation.

## 7. GPIO budget

| Signal | GPIO (BCM) | Pin |
|---|---|---|
| ROW1..ROW6 | 5, 6, 13, 19, 25, 8 | 29, 31, 33, 35, 22, 24 |
| COL1..COL5 | 12, 16, 20, 21, 7 | 32, 36, 38, 40, 26 |
| HK | 26 | 37 |
| Ringer HI / LO | 23, 24 | 16, 18 |
| USE LED | 17 | 11 |
| 5 V, GND | – | 2, 6 (and 9, 14, 20 spare GND) |

I2C (2, 3) and UART (14, 15) are left free for an MCP23017 or a future extra board.

## 8. Open questions for Hersh

1. Section 3 readings: keypad map (all 26 keys), hook pair, handset pairs, base speaker ohms.
2. Which of the 26 keys do you want live for the toddler? Suggested: 0-9 as today, M1-M9 as
   named speed dials, SOS = call a parent, everything else ignored.
3. Base cavity size, to decide whether the Pi 4 goes inside or sits beside the phone on a short
   cable bundle (either is fine; outside is easier to debug).

## 9. Measured values (fill in)

```
Ribbon pad count: ___      Keys: 26
Key -> (pad, pad):
 1: (__,__)  2: (__,__)  3: (__,__)
 4: (__,__)  5: (__,__)  6: (__,__)
 7: (__,__)  8: (__,__)  9: (__,__)
 *: (__,__)  0: (__,__)  #: (__,__)
 STORE (__,__) SPEAKER (__,__) REDIAL (__,__) FLASH (__,__)
 M1 (__,__) M2 (__,__) M3 (__,__) M4 (__,__) M5 (__,__)
 M6 (__,__) M7 (__,__) M8 (__,__) M9 (__,__) SOS (__,__)
Base speaker SPK+/SPK-: ___ Ω

Hook switch pins: ____  closed when handset is: [down | up]
Handset plug: contacts 1-4 -> wire colour -> pad:  ____________________
Receiver: ___ Ω      Mic: diode-mode ___ V forward, OL reverse  [yes/no]
Piezo B+/B-: ___     Base cavity: ___ x ___ x ___ mm
```
