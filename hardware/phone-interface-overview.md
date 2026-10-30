# Old phone into a Raspberry Pi: the short version

The plan in one picture:

```
   what the phone has              what we do with it                   where it lands on the Pi
   ─────────────────              ───────────────────                   ───────────────────────
   handset microphone  ──────▶  2 wires → 3.5 mm plug ──────────────▶  USB audio adapter, MIC jack
   handset earpiece    ──────▶  2 wires → 3.5 mm plug ──────────────▶  USB audio adapter, HEADPHONE jack
   26 keys (2 keypad boards) ─▶  ~11 wires off the ribbon pads ──────▶  GPIO pins (the Pi scans them)
   hook switch         ──────▶  2 wires ────────────────────────────▶  1 GPIO pin
   base speaker        ──────▶  2 wires → tiny $2 amplifier ◀───────   Pi's own headphone jack (ringtones)
   everything else on the main board (line jack, ringer chip, dialer chip, speakerphone chip)  →  left dead, never powered
```

## Why it works

A landline phone is only four simple things wrapped in a lot of 48-volt line circuitry: a
microphone, an earpiece, some switches, and a bell. The line circuitry exists to make those four
things work over two wires to the phone company. We are not using the phone company, so that
circuitry has no job. We bypass it entirely and connect the four simple things to the Pi with the
most ordinary interfaces there are: a USB sound card for audio and GPIO pins for switches.

- **Audio.** The handset's microphone is an electret capsule, the same kind inside a $10 USB
  headset. The USB audio adapter already supplies the small bias voltage it needs. The earpiece is a
  little speaker that the adapter's headphone output can drive directly. So the handset becomes a
  USB headset.
- **Keys.** The 26 keys are a grid of switches. The Pi puts a low signal on one column at a time
  and watches which row it shows up on; that tells it which key is down. About 11 wires, one 1 kΩ
  resistor each for safety, and a small scanning routine in the backend.
- **Hook switch.** A plain switch: one wire to a GPIO pin, one to ground.
- **Ringer.** The phone's own loudspeaker (it had a speakerphone) is fed by a $2 amplifier board
  from the Pi's headphone jack. Ringtones become WAV files, so the ring can be anything.

Nothing in the finished phone exceeds 5 volts.

## What gets kept, what gets cut

| Keep (mechanical and transducers) | Cut (line-side electronics) |
|---|---|
| Housing, handset, handset cord and jack | RJ11 line jack and its wires |
| Handset mic and earpiece | Both bridge rectifiers, varistor, zeners |
| Both keypad boards and their flex ribbons | `KA2411` ringer chip and the piezo disc |
| Hook switch | `U9` dialer chip (physically removed so it cannot load the key lines) |
| Base speaker, the "USE" LED, the two slide switches (optional) | `MC34018P` speakerphone chip and the base mic |

The main PCB stays in the phone as a carrier for the keypad ribbon and the hook switch. We solder
our wires onto its existing tinned pads and remove one chip. That is the entire board surgery.

## How it meets the software

A small SIP client program on the Pi (baresip, the `phone` service in Compose) uses the USB adapter
for audio and registers to Asterisk as "the phone". The backend tells it to dial when a key is
pressed off-hook, answers it when the handset lifts during a ring, and hangs up when the handset
drops. Asterisk, policies, recordings, features, and the parent app only ever see a SIP phone.

## The path, in order

1. **Measure** (multimeter, nothing cut): map which two ribbon pads each key connects, which hook
   switch pins close, confirm the handset pairs, and read the base speaker's resistance. Half an hour.
2. **Order** about $35 of parts: USB audio adapter, PAM8403 amp with a 3.5 mm input, screw-terminal
   3.5 mm plugs, jumper wires, a GPIO breakout, resistors, solder wick.
3. **Handset on the bench**: four wires into two screw-terminal 3.5 mm plugs, into the USB adapter,
   record and play back with `arecord`/`aplay`. First proof that audio works.
4. **Keys and hook on a breadboard**: remove `U9`, solder ~13 wires to the pads, run a test script
   that prints key names. First proof that input works.
5. **Ringer**: amp + base speaker on the Pi's headphone jack, play a ringtone.
6. **Software**: baresip as the phone leg, scanner and ringer in the backend, fakes for tests.
7. **Final build**: move the breadboard to a proto board, mount the Pi (inside the base if it fits,
   beside it if not), strain-relieve, reassemble, soak test with random key mashing.

Every stage has a pass/fail test before the next one starts. Details, schematics, BOM, and
measurement instructions: [phone-interface.md](phone-interface.md).

## Nice side effects

- Memory keys M1-M9 become one-press named speed dials (M1 = Grandma). SOS = call a parent.
- Custom ringtones and voice prompts can play from the base speaker without a call in progress.
- No 48 V or 90 V ring voltage anywhere a toddler can reach.
- About $35 of parts, and nothing in the phone needs configuring or can drift.
