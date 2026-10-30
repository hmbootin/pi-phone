# The first weekend

Goal: by Sunday night the phone has dial tone and pressing `7` tells the toddler a fun fact
(roadmap [M1](roadmap.md)). Real calls (M2) need a phone number, which takes a few days of
account approval, so start that signup on Friday and it'll be ready for next weekend.

## The week before: order things

From [hardware/bom.md](../hardware/bom.md):

- [ ] Grandstream **HT801 V2** (~$35)
- [ ] Raspberry Pi 4 4 GB (or Pi 5) + official PSU + fan case, unless you have one
- [ ] USB SSD (or a High Endurance microSD to start)
- [ ] Corded phone (AT&T CL2940 or VTech CD1113), or dust off a thrift-store one
- [ ] Two Ethernet cables long enough to reach the router
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
- [ ] `docker compose up -d` and confirm `docker compose ps` shows `asterisk` and `backend`
      healthy. Open `http://tincan.local:8080` and log in to the parent UI. Status should show
      Asterisk connected, phone unregistered, trunk unconfigured.

## Saturday morning (1 h): the ATA

- [ ] Plug the HT801 into Ethernet and power, phone into its PHONE port.
- [ ] Walk through [hardware/ata-setup.md](../hardware/ata-setup.md): find IP via `***` `02`,
      log in with the sticker password, set SIP server / user `phone` / password, dial plan `{x}`,
      PCMU, RFC2833, hook flash and call waiting off.
- [ ] On the Pi: `docker compose exec asterisk asterisk -rx "pjsip show endpoints"` shows `phone`
      with a contact. Parent UI shows phone **registered**.
- [ ] Lift handset: dial tone. If not, section 9 of ata-setup.md.

## Saturday afternoon (1 h): first feature

- [ ] In the parent UI, set digit 7 to "fun fact", topic "dinosaurs". Press *preview* to hear
      Piper render it in the browser.
- [ ] Press 7 on the phone. A fact. **M1 done.** Take a video.
- [ ] Press 6 for weather after setting the home location in Settings.
- [ ] Press "test call" in the UI: the phone rings; lift it, hear the test prompt.
- [ ] Add a contact for yourself (speed dial 1, your cell). Dialing 1 will fail politely with
      "trunk unconfigured" until next weekend. Check that the call shows up in the Calls list with
      outcome `failed`.

## Sunday (1 h): make it survive

- [ ] Reboot the Pi; confirm everything comes back without you (`docker compose ps`, phone
      re-registers within a minute, dial tone).
- [ ] Install Tailscale on your phone and open the UI from cellular.
- [ ] Set up backups: Backblaze B2 bucket + `rclone` crypt remote per deploy/README.md. Run the
      backup job once by hand and see `backup.last_ok_at` in the UI status.
- [ ] Set quiet hours and a 10-minute cap in Settings so they're in place before the first real call.
- [ ] Give the toddler the phone. Watch what they do with the buttons; that's your M3 feature list.

## Next weekend (M2)

- [ ] Provider approved your number: put the credentials in `.env` (see the pjsip shapes in
      research/voip-providers.md), `docker compose up -d`, UI shows trunk **registered**.
- [ ] Dial 1. Your cell rings with the new number as caller ID. Answer, talk, hang up.
      The recording appears in the UI; play it.
- [ ] Call the number from your cell. The phone rings. Then call it from a number that isn't a
      contact and confirm it's rejected politely.
- [ ] Register E911 on the number (it's $1-2/month and required in the US; if someone ever dials
      911 from the toddler phone the backend should forward it, and the address must be right).
