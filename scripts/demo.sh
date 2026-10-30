#!/usr/bin/env bash
# End-to-end demo with no hardware: backend + fake phone (keypad, hook, baresip) + fake Asterisk
# (ARI) + the built parent UI. Seeds a demo database, then drives a scripted day of calls the way
# the toddler would (lift the handset, press a key, hang up) through the real phone state machine,
# call router, policy and session code so the UI fills up with calls, outcomes and recordings.
#
#   mise run demo            # starts everything, runs the script, leaves the server up
#   DEMO_KEEP=0 mise run demo  # stop the server when the script finishes
#
# Open http://localhost:8080 (password: demo) while it runs.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PORT=${DEMO_PORT:-8080}
DATA=${DEMO_DATA_DIR:-$ROOT/data/demo}
BASE="http://localhost:$PORT"
JAR=$(mktemp)
log() { printf '\033[1;36m[demo]\033[0m %s\n' "$*"; }

rm -rf "$DATA"; mkdir -p "$DATA"
export TINCAN_FAKE_ARI=1 TINCAN_HARDWARE=fake TINCAN_DATA_DIR="$DATA" TINCAN_UI_DIR="$ROOT/ui/dist" TINCAN_PORT="$PORT"
export TINCAN_PARENT_PASSWORD=demo TINCAN_SECRET_KEY=demo-not-secret ARI_USER=demo ARI_PASSWORD=demo ARI_APP=tincan
export TINCAN_TIME_SCALE=${TINCAN_TIME_SCALE:-0.02}   # a 10-minute cap elapses in ~12 s

[[ -d "$ROOT/ui/dist" ]] || { log "ui/dist missing: building the UI"; (cd "$ROOT/ui" && pnpm build >/dev/null); }

cd "$ROOT/backend"
uv run tincan seed-demo >/dev/null
uv run tincan serve >"$DATA/server.log" 2>&1 &
SERVER=$!
cleanup() { [[ "${DEMO_KEEP:-1}" == "0" ]] && kill "$SERVER" 2>/dev/null; rm -f "$JAR"; }
trap cleanup EXIT

for _ in $(seq 1 50); do curl -fs "$BASE/healthz" >/dev/null 2>&1 && break; sleep 0.2; done
curl -fs "$BASE/healthz" >/dev/null || { log "backend did not start; see $DATA/server.log"; exit 1; }
curl -fs -c "$JAR" -o /dev/null -X POST "$BASE/api/auth/login" -H 'content-type: application/json' -d '{"password":"demo"}'

api() { curl -fs -b "$JAR" -H 'content-type: application/json' "$@"; }
sim() { api -X POST "$BASE/api/dev/simulate" -d "$1" >/dev/null; }
pause() { sleep "${1:-0.6}"; }
# The toddler's three moves. `press` takes a key name: 0-9, m1-m9, sos.
lift() { sim '{"event":"offhook"}'; pause 0.3; }
press() { sim "{\"event\":\"key\",\"key\":\"$1\"}"; }
hangup() { sim '{"event":"onhook"}'; }
phone() { api "$BASE/api/system/phone" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["state"], "offhook" if d["off_hook"] else "onhook")'; }

log "backend up on $BASE (parent UI password: demo)"
# The demo must behave the same at 1 am as at 1 pm: no quiet hours, generous caps.
api -X PATCH "$BASE/api/settings" -d '{"quiet_hours":null,"daily_call_cap":50,"max_call_minutes":10,"warning_seconds_before_end":60}' >/dev/null
log "phone: $(phone)"
log "1. toddler lifts the handset (dial tone) and presses 7: fun fact"
lift; press 7; pause 1.5; log "   phone: $(phone)"; hangup; pause

log "2. lifts, presses M1: calling Grandma, she answers, they chat, Grandma hangs up"
lift; press m1; pause 2; log "   phone: $(phone)"; sim '{"event":"hangup"}'; pause
log "   far end hung up while the handset is still lifted: 'call ended' tone, then dial tone: $(phone)"
hangup; pause

log "3. lifts, presses SOS: Mom, who is on do-not-disturb for an hour"
api -X POST "$BASE/api/contacts/1/dnd" -d '{"minutes":60}' >/dev/null
lift; press sos; pause 1.5; hangup; pause
api -X POST "$BASE/api/contacts/1/dnd" -d '{"clear":true}' >/dev/null

log "4. Grandma calls in; the base speaker rings; toddler lifts the handset; the call hits the time cap"
# (the ring timeout is scaled too: 25 s becomes 0.5 s, so lift the handset promptly)
sim '{"event":"inbound","from":"+15555550123"}'; sleep 0.15; log "   phone: $(phone)"; lift
log "   phone: $(phone)"
log "   (waiting for the scaled 10-minute cap: warning beep, then goodbye)"
for _ in $(seq 1 60); do
  a=$(api "$BASE/api/calls/active"); [[ "$a" == "null" ]] && break; sleep 0.5
done; hangup; pause

log "5. an unknown number calls: rejected, never rings"
sim '{"event":"inbound","from":"+15555559999"}'; pause 1.5; log "   phone: $(phone)"

log "6. lifts, presses 8: leaves Mom a secret message"
lift; press 8; pause 2; hangup; pause

log "7. lifts, presses 5: nothing is mapped there, friendly prompt"
lift; press 5; pause 1.5; hangup; pause

log "8. mashes keys with the handset down: nothing happens"
press 2; press sos; press 9; pause 0.3; log "   phone: $(phone)"

echo
log "call log:"
api "$BASE/api/calls?limit=20" | python3 "$ROOT/scripts/demo_summary.py" calls
log "recordings:"
api "$BASE/api/recordings" | python3 "$ROOT/scripts/demo_summary.py" recordings
echo
if [[ "${DEMO_KEEP:-1}" == "0" ]]; then log "done"; else
  log "server still running (pid $SERVER). Open $BASE  (password: demo). Ctrl-C or: kill $SERVER"
  wait "$SERVER"
fi
