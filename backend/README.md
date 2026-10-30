# Tin Can backend

Python service that owns every decision about a call: what a dialed digit means, whether the
call is allowed, bridging and recording through Asterisk's ARI, the local "features" (weather,
fun fact, secret message, mailbox), the recordings index, notifications, and the parent API
(`docs/api.md`). Asterisk itself is dumb; see `asterisk/etc/README.md`.

## Run it

```
cd backend
uv sync                       # python >= 3.11, uv
uv run tincan seed-demo       # two contacts, features on 6-9, default settings
TINCAN_FAKE_ARI=1 uv run tincan serve
```

Then `POST /api/auth/login {"password":"tincan"}` and drive the fake phone:

```
curl -c c.txt -XPOST localhost:8080/api/auth/login -H 'content-type: application/json' -d '{"password":"tincan"}'
curl -b c.txt -XPOST localhost:8080/api/dev/simulate -H 'content-type: application/json' -d '{"event":"offhook_dial","digit":"2"}'
curl -b c.txt -XPOST localhost:8080/api/dev/simulate -H 'content-type: application/json' -d '{"event":"hangup"}'
curl -b c.txt localhost:8080/api/calls
```

`/api/dev/simulate` events: `offhook_dial` (`digit`), `inbound` (`from`), `answer` (far end picks
up; the fake auto-answers after 10 ms anyway), `hangup` (everything). It only exists when
`TINCAN_FAKE_ARI=1`. Interactive API docs at `/api/docs`.

Tests and lint: `uv run pytest`, `uv run ruff check`, `uv run ruff format`.

CLI: `tincan serve | seed-demo | render-prompts | backup-done <id>...`.

## Environment variables

| Var | Default | What |
|-----|---------|------|
| `TINCAN_DATA_DIR` | `./data` (`/data` in Docker) | SQLite db, prompts cache, facts.json, secret key |
| `TINCAN_RECORDINGS_DIR` | `$TINCAN_DATA_DIR/asterisk/recording` | Where Asterisk's ARI recordings land (see mount contract) |
| `TINCAN_HOST` / `TINCAN_PORT` | `0.0.0.0` / `8080` | Listen address |
| `TINCAN_PARENT_PASSWORD` | `tincan` (warns) | The one parent password |
| `TINCAN_SECRET_KEY` | generated into `$TINCAN_DATA_DIR/secret_key` | Signs the session cookie |
| `TINCAN_UI_DIR` | unset (`/app/ui` in Docker) | Built parent app; served at `/` with SPA fallback when the dir exists |
| `TINCAN_FAKE_ARI` | `0` | `1` runs the in-process fake Asterisk and mounts `/api/dev/simulate` |
| `TINCAN_TIME_SCALE` | `1.0` | Multiplies call timers; tests use 0.01. Never set in production |
| `TINCAN_VERSION` | `dev` | Reported by `/api/system/status` (CI sets it to the tag) |
| `ARI_URL` | `http://localhost:8088` | Asterisk HTTP/ARI base URL (`http://asterisk:8088` in Compose) |
| `ARI_USER` / `ARI_PASSWORD` | `tincan` / `tincan` | Must match `asterisk/etc/ari.conf.tmpl` |
| `ARI_APP` | `tincan` | Stasis app name; must match `extensions.conf` |
| `PIPER_BIN` | `piper` | Piper CLI; if missing, prompts are a beep and a warning is logged |
| `PIPER_VOICE` | `en_US-lessac-medium` | Voice name (with `PIPER_DATA_DIR`) or path to a `.onnx` |
| `PIPER_DATA_DIR` | unset (`/opt/piper/voices` in Docker) | Where Piper looks for voices |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | unset | Optional email notifications (ntfy needs nothing) |

Auth: `POST /api/auth/login` sets an `itsdangerous`-signed `tincan_session` cookie (30 days).
Everything under `/api/` except login requires it; `/healthz` is public.

## How a call works

Asterisk's dialplan sends every call into the `tincan` Stasis app with args:

| Who | Dialplan | StasisStart args | Backend does |
|-----|----------|------------------|--------------|
| ATA dials `2` | `from-phone` | `dial,2` | speed dial -> contact -> policy -> originate `PJSIP/+1555...@trunk` (or `PJSIP/sip:...` for `sip:` contacts) with `appArgs=far` |
| Trunk delivers a call | `from-trunk` | `inbound` | caller ID -> contact -> policy -> originate `PJSIP/phone` with `appArgs=ring` |
| Backend test call | n/a | `test` | `POST /api/system/test-call` |

Channels, bridges, playbacks and recording names are all chosen by the backend (uuids), so the
session registers its waiter before issuing the request and never races the event. One
`CallSession` (`tincan/calls/session.py`) runs the flow; `tincan/calls/router.py` decides which
flow from the StasisStart args; `tincan/calls/policy.py` is pure and unit tested.

Policy outcomes are exactly the `docs/api.md` values and every attempt, rejected or not, is a
`calls` row. Notes on the edge cases:

- Toddler hangs up while the far end is still ringing -> `no_answer`.
- A disabled contact behaves like DND -> `rejected_dnd`.
- A digit with no contact and no feature (or a disabled feature) -> `rejected_unknown`,
  direction `feature`, and the phone hears "nothing is on that button".
- A second call while one is up -> `busy` for the new one; the first continues.
- The daily cap counts today's outbound rows (local time of `quiet_hours.tz`) that were not
  rejected. Inbound calls and features are not capped.
- Time cap: beep to the bridge at `max - warning_seconds_before_end`, then "Time's up! Bye bye!"
  to the bridge and hang up both legs -> `time_cap`. Per-contact `max_call_minutes` overrides.
- Inbound, known contact, nobody picks up in `ring_timeout_seconds`: the caller is offered a
  voicemail (kind `voicemail`, `contact_id` set); the mailbox feature (digit 9 by default) plays
  those back to the toddler. Unknown callers get `reject` or, with
  `unknown_caller_policy=voicemail`, a voicemail with `contact_id=null` for the parents.
- Anything that throws inside a flow is logged, the phone hears "Oops, that didn't work", the
  call is written as `failed`, and every channel/bridge/recording is cleaned up.

## File and mount contract with Asterisk

Both containers mount the same host directory at `/data`:

```
/data/
  tincan.db                    backend (SQLite, WAL)
  secret_key                   backend
  facts.json                   backend, seeded from tincan/features/facts_seed.json
  prompts/<sha>.wav            backend writes (Piper, 8 kHz s16 mono); Asterisk reads via sound:/data/prompts/<sha>
  asterisk/recording/          Asterisk writes (ARI stored recordings); backend reads, hashes, serves
    <yyyy>/<mm>/call-<call_id>.wav
    <yyyy>/<mm>/secret-<call_id>.wav
    <yyyy>/<mm>/voicemail-<call_id>.wav
```

Why `asterisk/recording` and not `recordings`: ARI stored recordings always go to
`<astspooldir>/recording/<name>.<format>`; there is no separate directive. `asterisk.conf` sets
`astspooldir => /data/asterisk`. The backend passes `name=<yyyy>/<mm>/call-<id>` and creates the
year/month directory on the shared mount before starting the recording, so the file lands at
`/data/asterisk/recording/<yyyy>/<mm>/call-<id>.wav`. `recordings.path` in the database is the
relative part (`<yyyy>/<mm>/call-<id>.wav`). Override with `TINCAN_RECORDINGS_DIR` if you move
the spool dir.

Permissions: the backend runs as uid 1000 and Asterisk writes as its own user. Run both with the
same uid/gid (Compose `user:`) or make `/data` group-writable, otherwise recording files will be
unreadable to the backend and prompts unreadable to Asterisk.

Audio format: ARI bridge recordings are one mixed mono WAV. True stereo (phone left, far end
right) is a MixMonitor option (`t()`/`r()` streams) that ARI does not expose; `docs/architecture.md`
mentions stereo as the goal, this implementation is honest about mono. Prompts and the shipped
`beep.wav` are 8 kHz 16-bit mono so Asterisk's `format_wav` plays them without transcoding.

Playback media URIs are absolute: `sound:/data/prompts/<sha>` (Asterisk appends `.wav`). This
only works because the path is the same in both containers.

## Backups

The backend never copies files. The `backup` sidecar (`deploy/`) runs rclone over
`/data/asterisk/recording` (copy, never move) and then reports:

- `GET /api/system/backup/pending` -> `[{"id","path","sha256"}]` not yet backed up
- `POST /api/system/backup-report {"ids":[...], "ok":true}` marks them and stamps `last_ok_at`
- or, without the API: `tincan backup-done <id>...` against the same `/data`

`GET /api/system/status` reports `backup.pending` and `backup.last_ok_at`.

## Adding a feature

1. `tincan/features/my_thing.py`: subclass `Feature`, set `kind = "my_thing"`, implement
   `text(rt, config)` (used by the preview endpoint and the default `run`). Override
   `run(session, config)` only if you need more than "say something": `session.say`,
   `session.play`, `session.beep`, `session.record_until_hangup`, `session.rt.notify`.
2. Add it to `FEATURES` in `tincan/features/registry.py`.
3. Put the spoken strings in `tincan/tts/prompts.py`.
4. Add the kind to `FeatureIn.kind` in `tincan/schemas.py` (and to `docs/api.md`).
5. Test it in `tests/test_features_flow.py` with `ari.dial("<digit>")` + `settle(rt)`.

## Docker

Build from the repo root (the Dockerfile copies `backend/` and optionally `ui/dist`):

```
docker build -f backend/Dockerfile -t tincan-backend .
docker build -f backend/Dockerfile --build-arg UI_DIST=local -t tincan-backend .   # with the built UI
```

The image installs `piper-tts` and downloads `en_US-lessac-medium` at build time; if the download
fails the build still succeeds and prompts fall back to a beep until a voice is mounted at
`/opt/piper/voices`. The container runs `tincan serve` as uid 1000 and expects `/data` mounted.
