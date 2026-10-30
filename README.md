# Tin Can

A "tin can and string" landline for a toddler. An ordinary cheap landline phone, unmodified on the
outside, that can call a short list of family and friends over the internet, ring when they call back,
and record every call as an audio memory. Extra dial keys do fun things: hear the weather, learn a
fact, leave a secret message for a parent.

Everything runs self-hosted on a Raspberry Pi 4 at home. The only cloud pieces are the ones that
can't be avoided (a phone number on the public phone network) or that protect the memories (off-site
backup of recordings). See [docs/architecture.md](docs/architecture.md).

```
                     ┌──────────────── Raspberry Pi 4 ────────────────┐
 ┌───────┐  RJ11   ┌────────┐  SIP/RTP  │ ┌──────────┐  ARI  ┌───────────────┐ │   SIP trunk   ┌──────────┐
 │ phone ├─────────┤  ATA   ├───────────┼─┤ Asterisk ├───────┤ tincan backend│ ├───────────────┤ provider │──▶ family's
 └───────┘ analog  └────────┘  Ethernet │ └────┬─────┘       │ + parent UI   │ │  (internet)   └──────────┘    phones
                                        │      │ recordings   └───────┬───────┘ │
                                        │      ▼                      ▼         │
                                        │   /data/recordings  ──▶  off-site backup (rclone)
                                        └───────────────────────────────────────┘
```

## Repository layout

| Path | What |
|------|------|
| `docs/` | Architecture, decisions (`adr/`), hardware, signal path, API contract, runbooks |
| `hardware/` | Bill of materials, wiring, the analog phone interface |
| `firmware/pico/` | The original Pico 2 W experiment (dial/hook sensing). Kept for the v2 DIY line interface. |
| `asterisk/` | Asterisk configuration: thin dialplan that hands every call to the backend |
| `backend/` | Python service: call control (ARI), contacts, policies, features, recordings, parent API |
| `ui/` | Parent web app (React + Vite), built into the backend image |
| `deploy/` | Pi bootstrap, Docker Compose, OTA updates, backups, Tailscale |
| `.github/workflows/` | CI: tests, lint, multi-arch image build, release |

## Quick start (developer laptop)

```
mise install          # python, uv, node, pnpm
mise run setup        # install backend + ui deps
mise run test         # backend + ui tests
mise run dev          # backend on :8080 with a fake Asterisk, ui on :5173
```

## Quick start (the Pi)

See [deploy/README.md](deploy/README.md). Short version: flash Raspberry Pi OS Lite 64-bit, run
`deploy/bootstrap.sh` once, then every later update is `mise run release` from your laptop.

## Demo without hardware

`mise run demo` starts the backend against an in-process fake Asterisk, serves the built parent app
on http://localhost:8080 (password `demo`), and drives a scripted day: a fun fact, a call to Grandma
with a recording, a do-not-disturb rejection, an inbound call that hits the time cap, an unknown
caller turned away, and a secret message for Mom.

<p>
<img src="docs/images/home.png" width="200" alt="Home: line status and today's calls">
<img src="docs/images/dial.png" width="200" alt="Dial pad: what each digit does">
<img src="docs/images/contacts.png" width="200" alt="Contacts with do-not-disturb">
<img src="docs/images/memories.png" width="200" alt="Memories: recordings to listen to">
</p>

## Status

Experimental branch `tin-can-landline`. Nothing here has touched real hardware yet beyond the Pico
button test. See [docs/roadmap.md](docs/roadmap.md) for the build order and
[docs/first-weekend.md](docs/first-weekend.md) for what to buy and do first.
