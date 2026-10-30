#!/usr/bin/env bash
# Nightly off-site backup. Run on the Pi host by tincan-backup.timer, or by hand:
#   sudo /opt/tincan/backup.sh
#
# What it does, in order:
#   1. Snapshot /data/tincan.db to /data/backup/tincan.db with SQLite's online backup API
#      (consistent even while the backend is writing). Uses the backend container's Python so
#      the host needs no sqlite3 package.
#   2. `rclone copy` /data/recordings, /data/asterisk/recording, /data/prompts and the DB snapshot to $RCLONE_REMOTE using
#      the rclone sidecar in compose.yaml. copy, never sync/move: nothing remote is ever deleted.
#   3. If the backend exposes a "mark backed up" endpoint, tell it which recordings are now
#      off-site so the UI can show backed_up_at. Absent endpoint = skipped, not an error.
#
# Exit status is non-zero if any copy failed, so `systemctl status tincan-backup` shows it.
set -euo pipefail

TINCAN_DIR=${TINCAN_DIR:-/opt/tincan}
cd "$TINCAN_DIR"

# shellcheck disable=SC1091
set -a; [[ -f .env ]] && . ./.env; set +a
DATA_DIR=${TINCAN_DATA_DIR:-/data}
OPT_DIR=${TINCAN_OPT_DIR:-/opt/tincan}
REMOTE=${RCLONE_REMOTE:-tincan-backup:}
BACKEND_URL=${BACKEND_URL:-http://127.0.0.1:8080}

compose() { docker compose -f "$TINCAN_DIR/compose.yaml" "$@"; }
log() { printf '[backup] %s\n' "$*"; }

if [[ ! -f "${TINCAN_RCLONE_CONF:-$TINCAN_DIR/rclone.conf}" ]]; then
  log "no rclone.conf at ${TINCAN_RCLONE_CONF:-$TINCAN_DIR/rclone.conf}; see deploy/rclone.conf.example"
  exit 2
fi

# 1. Database snapshot. Python's sqlite3 module wraps sqlite3_backup(); the backend image has it.
mkdir -p "$DATA_DIR/backup"
if compose ps --status running backend >/dev/null 2>&1 && [[ -f "$DATA_DIR/tincan.db" ]]; then
  compose exec -T backend python3 - <<'PY'
import sqlite3, os
src = sqlite3.connect("file:/data/tincan.db?mode=ro", uri=True)
dst = sqlite3.connect("/data/backup/tincan.db.tmp")
with dst:
    src.backup(dst)
dst.close(); src.close()
os.replace("/data/backup/tincan.db.tmp", "/data/backup/tincan.db")
PY
  log "snapshotted tincan.db"
elif command -v sqlite3 >/dev/null && [[ -f "$DATA_DIR/tincan.db" ]]; then
  sqlite3 "$DATA_DIR/tincan.db" ".backup '$DATA_DIR/backup/tincan.db.tmp'"
  mv "$DATA_DIR/backup/tincan.db.tmp" "$DATA_DIR/backup/tincan.db"
  log "snapshotted tincan.db (host sqlite3)"
else
  log "backend not running and no sqlite3 on host; skipping DB snapshot"
fi

# 2. Copy. --immutable: a file that changed since the last copy is an error, not an overwrite
# (recordings are immutable by rule). Not used for the DB snapshot, which changes nightly.
status=0
rc() { compose run --rm --no-deps backup "$@"; }
# asterisk/recording is where ARI-driven recordings land (astspooldir=/data/asterisk).
for sub in recordings asterisk/recording prompts; do
  if [[ -d "$DATA_DIR/$sub" ]]; then
    log "copying $sub"
    rc copy --immutable --stats-one-line --stats 0 "/data/$sub" "${REMOTE}${sub}" || status=$?
  fi
done
if [[ -f "$DATA_DIR/backup/tincan.db" ]]; then
  log "copying tincan.db snapshot"
  rc copy --stats-one-line --stats 0 /data/backup/tincan.db "${REMOTE}db" || status=$?
  # Keep dated copies too, so a corrupt DB that gets backed up doesn't clobber the only good one.
  rc copyto --stats-one-line --stats 0 /data/backup/tincan.db "${REMOTE}db/tincan-$(date +%F).db" || status=$?
fi

# 3. Tell the backend which recordings are now safe. The backend tracks backup state per
#    recording: GET /api/system/backup/pending lists ids, POST /api/system/backup-report marks
#    them. Both need the parent session cookie, so log in first with TINCAN_PARENT_PASSWORD
#    from /opt/tincan/.env. Any failure here is a warning; the copy already succeeded.
if [[ $status -eq 0 ]]; then
  jar=$(mktemp); trap 'rm -f "$jar"' EXIT
  pw=$(sed -n 's/^TINCAN_PARENT_PASSWORD=//p' "$OPT_DIR/.env" 2>/dev/null || true)
  if curl -fsS -c "$jar" -o /dev/null -X POST "$BACKEND_URL/api/auth/login" \
      -H 'content-type: application/json' -d "{\"password\":\"$pw\"}"; then
    ids=$(curl -fsS -b "$jar" "$BACKEND_URL/api/system/backup/pending" | sed -E 's/[^0-9,]//g; s/,+/,/g; s/^,|,$//g')
    if [[ -n "$ids" ]]; then
      curl -fsS -b "$jar" -o /dev/null -X POST "$BACKEND_URL/api/system/backup-report" \
        -H 'content-type: application/json' -d "{\"ids\":[$ids],\"ok\":true}" \
        && log "marked recordings $ids as backed up" || log "warning: backup-report failed"
    else
      log "no pending recordings to mark"
    fi
  else
    log "warning: could not log in to backend; recordings stay marked pending"
  fi
  date -u +%FT%TZ > "$DATA_DIR/backup/last_ok"
  log "done"
else
  log "FAILED (rclone exit $status)"
fi
exit $status
