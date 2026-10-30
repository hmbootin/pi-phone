#!/usr/bin/env bash
# Tin Can OTA update. Run by tincan-update.timer every 10 minutes, or by hand on the Pi:
#
#   sudo /opt/tincan/update.sh                 # follow the channel (default: stable)
#   sudo /opt/tincan/update.sh --version v1.2.0  # pin to a release and switch to it now
#   sudo /opt/tincan/update.sh --rollback      # go back to whatever ran before the last update
#   sudo /opt/tincan/update.sh --check         # print what would happen, change nothing
#
# How it decides:
#   /opt/tincan/channel   holds "stable" or a fixed tag. "stable" means the newest GitHub
#                         release tag of $GITHUB_REPO (fetched via the public API; falls back
#                         to the `stable` image tag's digest if the API is unreachable).
#   /opt/tincan/.env      TINCAN_VERSION= is what compose actually runs. This script is the
#                         only thing that rewrites that line.
#   /opt/tincan/.previous-version   the TINCAN_VERSION before the last successful update,
#                         used by --rollback. Only one step of history; releases are tags, so
#                         `--version vX.Y.Z` reaches anything older.
#
# After `compose up -d` it waits for the backend healthcheck. If that fails it automatically
# rolls back to the previous version and exits non-zero, so the journal shows it.
set -euo pipefail

TINCAN_DIR=${TINCAN_DIR:-/opt/tincan}
ENV_FILE="$TINCAN_DIR/.env"
CHANNEL_FILE="$TINCAN_DIR/channel"
PREV_FILE="$TINCAN_DIR/.previous-version"
COMPOSE=(docker compose -f "$TINCAN_DIR/compose.yaml")
GITHUB_REPO=${GITHUB_REPO:-}
HEALTH_WAIT=${HEALTH_WAIT:-120}

log() { printf '[update] %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || die "$ENV_FILE not found; run deploy/bootstrap.sh first"

env_get() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n1; }
env_set() {
  # Replace or append KEY=value in .env without touching anything else.
  if grep -q "^$1=" "$ENV_FILE"; then
    sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$1" "$2" >>"$ENV_FILE"
  fi
}

current=$(env_get TINCAN_VERSION)
owner=$(env_get GHCR_OWNER)
[[ -n "$owner" ]] || die "GHCR_OWNER missing from $ENV_FILE"
GITHUB_REPO=${GITHUB_REPO:-$owner/pi-phone}
channel=stable
[[ -f "$CHANNEL_FILE" ]] && channel=$(tr -d '[:space:]' <"$CHANNEL_FILE")

mode=channel
target=""
check_only=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) mode=pin; target=$2; shift 2 ;;
    --version=*) mode=pin; target=${1#--version=}; shift ;;
    --rollback) mode=rollback; shift ;;
    --check) check_only=1; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

latest_release() {
  # Newest non-prerelease tag, e.g. v1.4.2. Unauthenticated: 60 req/h is plenty for a 10-min timer.
  curl -fsSL --max-time 20 -H 'Accept: application/vnd.github+json' \
    "https://api.github.com/repos/$GITHUB_REPO/releases/latest" \
    | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n1
}

case "$mode" in
  pin)
    [[ "$target" =~ ^v[0-9]+\.[0-9]+\.[0-9]+ ]] || die "--version wants a tag like v1.2.0 (got '$target')"
    echo "$target" >"$CHANNEL_FILE"
    ;;
  rollback)
    [[ -s "$PREV_FILE" ]] || die "no previous version recorded in $PREV_FILE"
    target=$(cat "$PREV_FILE")
    echo "$target" >"$CHANNEL_FILE"   # pin so the next timer run doesn't re-upgrade
    log "rolling back $current -> $target (channel pinned to $target; edit $CHANNEL_FILE to resume stable)"
    ;;
  channel)
    if [[ "$channel" == "stable" ]]; then
      target=$(latest_release || true)
      if [[ -z "$target" ]]; then
        log "GitHub API unreachable; comparing the :stable image digest instead"
        target=stable
      fi
    else
      target=$channel
    fi
    ;;
esac

if [[ "$target" == "stable" ]]; then
  # Digest comparison path: pull :stable and see whether anything changed.
  before=$(docker image inspect --format '{{index .RepoDigests 0}}' "ghcr.io/$owner/tincan-backend:stable" 2>/dev/null || true)
  [[ $check_only -eq 1 ]] && { log "would pull ghcr.io/$owner/*:stable (current digest ${before:-none})"; exit 0; }
  docker pull -q "ghcr.io/$owner/tincan-backend:stable" >/dev/null
  docker pull -q "ghcr.io/$owner/tincan-asterisk:stable" >/dev/null
  after=$(docker image inspect --format '{{index .RepoDigests 0}}' "ghcr.io/$owner/tincan-backend:stable")
  if [[ "$current" == "stable" && "$before" == "$after" ]]; then
    log "stable unchanged ($after)"; exit 0
  fi
fi

if [[ "$target" == "$current" && "$mode" != "rollback" ]]; then
  log "already on $current (channel: $channel)"
  exit 0
fi

log "update: $current -> $target (channel: $channel)"
[[ $check_only -eq 1 ]] && exit 0

# Pull first so a failed download leaves the running version untouched.
docker pull -q "ghcr.io/$owner/tincan-backend:$target" >/dev/null || die "pull backend:$target failed"
docker pull -q "ghcr.io/$owner/tincan-asterisk:$target" >/dev/null || die "pull asterisk:$target failed"

[[ "$mode" != "rollback" ]] && echo "$current" >"$PREV_FILE"
env_set TINCAN_VERSION "$target"
"${COMPOSE[@]}" up -d --remove-orphans

healthy() {
  local cid
  cid=$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)
  [[ -n "$cid" ]] && [[ "$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null)" == "healthy" ]]
}
for ((i = 0; i < HEALTH_WAIT; i += 5)); do
  healthy && { log "backend healthy on $target"; docker image prune -f >/dev/null 2>&1 || true; exit 0; }
  sleep 5
done

log "backend not healthy after ${HEALTH_WAIT}s on $target"
if [[ "$mode" != "rollback" && -s "$PREV_FILE" ]]; then
  prev=$(cat "$PREV_FILE")
  log "rolling back to $prev"
  env_set TINCAN_VERSION "$prev"
  echo "$prev" >"$CHANNEL_FILE"
  "${COMPOSE[@]}" up -d --remove-orphans || true
  die "update to $target failed; rolled back to $prev and pinned channel. Fix, then: echo stable > $CHANNEL_FILE"
fi
die "update to $target failed and no rollback available"
