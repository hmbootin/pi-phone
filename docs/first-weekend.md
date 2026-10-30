# The first weekend

Goal: by Sunday night the handset, keys and ringer all work on the bench against the Pi
(roadmap [M1](roadmap.md)), and if the software is ready, pressing `7` tells the toddler a fun
fact (M2). Real calls (M3) need a phone number, which takes a few days of account approval, so
start that signup on Friday and it'll be ready for next weekend.

## The week before: measure and order

- [ ] Do the multimeter survey in [hardware/phone-interface.md](../hardware/phone-interface.md) §3:
      keypad map (all 26 keys), hook switch pair, handset pairs, base speaker ohms. Fill in §9.
- [ ] Order from [hardware/bom.md](../hardware/bom.md): USB audio adapter, screw-terminal 3.5 mm
      plugs, PAM8403 amp with a 3.5 mm input, jumper wires, 1 kΩ resistors, GPIO breakout, solder wick.
- [ ] Official PSU and a USB SSD (or a High Endurance microSD to start), if the Pi lacks them.
- [ ] An Ethernet cable long enough to reach the router.
- [ ] Sign up with a trunk provider and order a number (recommendation and prices in
      [research/voip-providers.md](research/voip-providers.md)). KYC/approval can take 1-3 days.
      Put $10-20 on the account.

## Friday evening (30 min): the Pi

- [ ] Flash Raspberry Pi OS Lite 64-bit to the SSD/SD with Raspberry Pi Imager; set hostname
      `tincan`, your user, SSH key, and Wi-Fi *off* (it's wired).
- [ ] Boot it on Ethernet, `ssh tincan.local`.
- [ ] Follow [deploy/README.md](../deploy/README.md): run `deploy/bootstrap.sh` (installs Docker,
      Tailscale, creates `/data`, writes `.env`). Generate `PHONE_SIP_PASSWORD` and the parent
      password when it asks.
- [ ] `docker compose up -d` and confirm `docker compose ps` shows `asterisk`, `phone` and
      `backend` healthy. Open `http://tincan.local:8080` and log in to the parent UI. Status should
      show Asterisk connected, phone unregistered, trunk unconfigured.

## Saturday (3 h): the phone, stage by stage

Follow [hardware/phone-interface.md](../hardware/phone-interface.md) §6; each stage has its own
pass test.

- [ ] Stage 1: handset wires into two screw-terminal plugs, into the USB adapter, into the Pi.
      `arecord` five seconds, `aplay` it back into the earpiece.
- [ ] Stage 2: clip the legs off `U9`, solder jumper leads to the keypad pads and hook switch,
      breadboard with 1 kΩ per line. The key-scan script prints every key once; no ghosting.
- [ ] Stage 3: base speaker on the amp, amp on the Pi headphone jack. `aplay` a ringtone.
- [ ] With the `phone` and `backend` services up: `docker compose exec asterisk asterisk -rx
      "pjsip show endpoints"` shows `phone` with a contact. Parent UI shows phone **registered**.
- [ ] Lift handset: dial tone from the backend. **M1 done.**

## Saturday evening (1 h): first feature

- [ ] In the parent UI, set digit 7 to "fun fact", topic "dinosaurs". Press *preview* to hear
      Piper render it in the browser.
- [ ] Press 7 on the phone. A fact. **M2 done.** Take a video.
- [ ] Press 6 for weather after setting the home location in Settings.
- [ ] Press "test call" in the UI: the base speaker rings; lift the handset, hear the test prompt.
- [ ] Add a contact for yourself (memory key M1, your cell). Pressing M1 will fail politely with
      "trunk unconfigured" until next weekend. Check that the call shows up in the Calls list with
      outcome `failed`.

## Sunday (1 h): make it survive

- [ ] Reboot the Pi with the handset off-hook; confirm everything comes back without you
      (`docker compose ps`, phone re-registers within a minute, dial tone, no auto-dial).
- [ ] Install Tailscale on your phone and open the UI from cellular.
- [ ] Set up backups: Backblaze B2 bucket + `rclone` crypt remote per deploy/README.md. Run the
      backup job once by hand and see `backup.last_ok_at` in the UI status.
- [ ] Set quiet hours and a 10-minute cap in Settings so they're in place before the first real call.
- [ ] Give the toddler the phone. Watch what they do with the buttons; that's your M3 feature list.

## Next weekend (M3)

- [ ] Provider approved your number: put the credentials in `.env` (see the pjsip shapes in
      research/voip-providers.md), `docker compose up -d`, UI shows trunk **registered**.
- [ ] Press M1. Your cell rings with the new number as caller ID. Answer, talk, hang up.
      The recording appears in the UI; play it.
- [ ] Call the number from your cell. The base speaker rings. Then call it from a number that isn't a
      contact and confirm it's rejected politely.
- [ ] Register E911 on the number (it's $1-2/month and required in the US; if someone ever dials
      911 from the toddler phone the backend should forward it, and the address must be right).
