# Roadmap

Each milestone ends with something the toddler can hold.

## M0 Desk prototype (this branch)
- [x] Repo layout, architecture, API contract, ADRs
- [x] Backend with fake ARI, policies, features, parent API, tests
- [x] Parent UI
- [x] Asterisk config, Compose, bootstrap, CI
- [x] `mise run demo` end-to-end against the fake Asterisk
- [x] Source the phone, photograph the boards
- [ ] Measure the keypad map, hook switch, handset and base speaker (`hardware/phone-interface.md` §3)
- [ ] Order the interface parts (`hardware/bom.md`)

## M1 Handset on the bench
- Handset mic and earpiece on the USB adapter: `arecord`/`aplay` round trip.
- Keys and hook on GPIO: a test script prints every key name, no ghosting.
- Base speaker on the amp plays a ringtone from the Pi's headphone jack.

## M2 Dial tone
- `phone` service (baresip) and the backend hardware service in Compose; `pjsip show endpoints`
  shows `phone`; lifting the handset gives dial tone.
- Press `7` → hear a fun fact. Proves keys → backend → baresip → Asterisk → backend → Piper → playback.

## M3 First real call
- Trunk configured. Press `M1` → Mom's cell rings. Recording lands in `/data/recordings`, shows in UI.
- Mom calls the number → base speaker rings → toddler answers.

## M4 Daily driver
- Everything off the breadboard, Pi mounted, phone reassembled; 24 h key-mashing soak test.
- Time cap, quiet hours, DND, backups verified by restoring one file, ntfy notifications.
- Secret message (8), mailbox (9), weather (6).

## M5 Nice to have
- Per-contact ringtones; the keypad's "USE" LED as an in-call light.
- SMS "DND 2h" via Tailscale Funnel.
- Weekly "memories" email with the week's recordings.
