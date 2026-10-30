# Roadmap

Each milestone ends with something the toddler can hold.

## M0 Desk prototype (this branch)
- [x] Repo layout, architecture, API contract, ADRs
- [x] Backend with fake ARI, policies, features, parent API, tests
- [x] Parent UI
- [x] Asterisk config, Compose, bootstrap, CI
- [x] `mise run demo` end-to-end against the fake Asterisk
- [ ] Order hardware (`hardware/bom.md`)

## M1 Dial tone
- Pi running Compose, ATA registered, phone gets dial tone, `pjsip show endpoints` shows `phone`.
- Dial `7` → hear a fun fact. Proves ATA → Asterisk → backend → Piper → playback.

## M2 First real call
- Trunk configured. Dial `1` → Mom's cell rings. Recording lands in `/data/recordings`, shows in UI.
- Mom calls the number → phone rings → toddler answers.

## M3 Daily driver
- Time cap, quiet hours, DND, backups verified by restoring one file, ntfy notifications.
- Secret message (8), mailbox (9), weather (6).

## M4 Nice to have
- Pico as extra-button controller (big "call Mom" button) over Wi-Fi.
- SMS "DND 2h" via Tailscale Funnel.
- Weekly "memories" email with the week's recordings.
- DIY SLIC line interface (`hardware/diy-line-interface.md`).
