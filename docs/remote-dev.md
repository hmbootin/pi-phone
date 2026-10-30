# Remote development on the Pi

Claude Code (and you) run on the laptop. The Pi only ever runs containers and gets files pushed
to it. Nothing is installed on the Pi beyond what `deploy/bootstrap.sh` sets up.

## Reaching the Pi

`bootstrap.sh` runs `tailscale up --ssh`, so any device on your tailnet can `ssh pi@tincan` with
no keys: Tailscale authenticates you. Add to `~/.ssh/config` so tools, rsync and Claude Code all
agree on one name:

```
Host tincan
  HostName tincan            # MagicDNS; or tincan.<tailnet>.ts.net, or the 100.x.y.z IP
  User pi                    # whatever you chose in the Imager
  ServerAliveInterval 30
```

Check: `ssh tincan uptime`. If MagicDNS doesn't resolve, `tailscale status` on the laptop lists
the Pi's 100.x address; put that in `HostName`.

The mise tasks use `TINCAN_PI_HOST` (default `tincan`) and `TINCAN_PI_USER` (default `pi`).
Override per shell: `TINCAN_PI_HOST=192.168.1.50 mise run logs`.

## The loop

| Task | What it does |
|------|--------------|
| `mise run pi -- <cmd>` | Runs `<cmd>` on the Pi. `mise run pi -- docker ps`, `mise run pi -- sudo /opt/tincan/update.sh --check`. |
| `mise run logs [-- service]` | `docker compose logs -f` on the Pi. `mise run logs -- backend`. |
| `mise run deploy-dev` | Builds the UI locally, rsyncs the repo to `/opt/tincan/src` on the Pi, builds both images **on the Pi** (native arm64, minutes for backend, ~40 min the first time for Asterisk, then cached) and `up -d`s them using the real `/opt/tincan/.env`. No tag, no CI. |
| `mise run deploy-release` | Puts the Pi back on the released images from `.env`'s `TINCAN_VERSION`. |
| `mise run release -- v1.2.3` | The real path: tag, CI builds, Pi auto-updates in ≤10 min. |

A typical Claude Code session on a backend bug: edit in `backend/`, `mise run test`, `mise run
deploy-dev`, `mise run logs -- backend`, dial from the toddler phone, read the log, repeat. Claude
Code can run all of those itself; the Pi never needs an editor or a Python install.

`deploy-dev` tags images `tincan-*:dev` and the compose override uses `pull_policy: never`, so
`tincan-update.timer` won't fight you: it only rewrites `TINCAN_VERSION` in `.env` and runs
`compose up` with `compose.yaml` alone, which brings the released images back. If you want the
timer out of the way for a long session: `mise run pi -- sudo systemctl stop tincan-update.timer`
(and `start` it after).

## Watching Asterisk

```
mise run pi -- docker compose -f /opt/tincan/compose.yaml exec asterisk asterisk -rvvv
```

gives the Asterisk console (Ctrl-C to leave; it doesn't stop Asterisk). Useful there:

```
pjsip show endpoints
pjsip set logger on          # full SIP trace
rtp set debug on             # every RTP packet (noisy; `rtp set debug off`)
core show channels
ari show apps                # tincan should be listed once the backend is connected
```

One-shot: `mise run pi -- docker compose -f /opt/tincan/compose.yaml exec asterisk asterisk -rx '"pjsip show endpoints"'`.

## Simulating calls on the laptop

The backend has a fake ARI (`backend/tincan/ari/fake.py`); `mise run dev` starts it with
`TINCAN_FAKE_ARI=1`, so the whole policy/feature path runs with no Asterisk anywhere. The fake
exposes the same ARI the backend drives, so a "call" is a scripted sequence of events. The
endpoints:

```
mise run dev                                   # backend :8080, ui :5173
# log in once (dev password is "tincan"), keep the cookie
curl -c jar -X POST localhost:8080/api/auth/login -H 'content-type: application/json' -d '{"password":"tincan"}'
# toddler lifts the handset and dials 2
curl -b jar -X POST localhost:8080/api/dev/simulate -H 'content-type: application/json' -d '{"event":"offhook_dial","digit":"2"}'
# the far end answers; later someone hangs up
curl -b jar -X POST localhost:8080/api/dev/simulate -H 'content-type: application/json' -d '{"event":"answer"}'
curl -b jar -X POST localhost:8080/api/dev/simulate -H 'content-type: application/json' -d '{"event":"hangup"}'
# grandma calls in
curl -b jar -X POST localhost:8080/api/dev/simulate -H 'content-type: application/json' -d '{"event":"inbound","from":"+15555550123"}'
```

`mise run demo` runs that whole sequence (plus a fun fact and a time-capped call) against a fresh
demo database, so you can watch the UI fill up. `/api/dev/simulate` only exists with
`TINCAN_FAKE_ARI=1`.

and watch `GET /api/events` (SSE) or the UI's call log. `TINCAN_TIME_SCALE=0.01` makes a 10-minute
cap elapse in 6 seconds. In pytest the same fake is a fixture; prefer a test over a curl session
when you're fixing policy logic.

Against the real Pi, a test call is `POST /api/system/test-call` from the UI (System → Test call),
or physically: lift the handset.

## Files on the Pi, for orientation

```
/opt/tincan/            compose.yaml, .env, channel, update.sh, backup.sh, rclone.conf
/opt/tincan/src/        your rsynced checkout (deploy-dev only)
/data/                  tincan.db, recordings/, prompts/, asterisk/recording/, backup/
journalctl -u tincan -u tincan-update -u tincan-backup
```
