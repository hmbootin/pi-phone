# Tin Can (monorepo)

Toddler landline over the internet: gutted landline phone -> Pi GPIO + USB audio -> baresip -> Asterisk -> Python backend -> SIP trunk.
Read `docs/architecture.md` first. Decisions live in `docs/adr/`; add an ADR before reversing one.

## Layout

- `backend/` Python 3.12, FastAPI, SQLite. Call control talks to Asterisk over ARI. `uv` manages deps.
- `ui/` React + Vite + TypeScript parent app. `pnpm`. Talks to the backend over `docs/api.md`.
- `asterisk/` config. The dialplan is intentionally dumb: every call enters the `tincan` Stasis app.
- `hardware/` the phone teardown, wiring, BOM. `deploy/` Docker Compose for the Pi, bootstrap, OTA, backup.
  `firmware/pico/` is the old Pico work, unused.

## Commands (run from repo root)

- `mise run setup`, `mise run test`, `mise run lint`, `mise run dev`.
- `mise run pi -- <cmd>` runs a command on the Pi over Tailscale SSH. `mise run release` ships a build.
- Backend only: `cd backend && uv run pytest`. UI only: `cd ui && pnpm test`.

## Rules

- No real Asterisk, GPIO or baresip in unit tests. The backend has a fake ARI (`backend/tests/fake_ari.py`);
  the hardware service gets the same treatment.
- Contacts, policies, and features live in SQLite, never in Asterisk config. Asterisk config is static
  apart from trunk credentials, which come from env at container start.
- Recordings are immutable once written. Never delete them from code; the backup job copies, never moves.
- Anything the toddler can trigger must be safe when it fails: fall back to a friendly audio prompt,
  never silence, never an open line to an unknown number.
