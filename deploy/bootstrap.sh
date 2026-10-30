#!/usr/bin/env bash
# One-time setup of a fresh Raspberry Pi OS Lite (64-bit) for Tin Can. Idempotent: re-running
# it is safe and is how you repair a half-finished run.
#
#   git clone https://github.com/<owner>/pi-phone && cd pi-phone
#   sudo GHCR_OWNER=<owner> ./deploy/bootstrap.sh
#
# or without git, straight from a release:
#   curl -fsSL https://raw.githubusercontent.com/<owner>/pi-phone/main/deploy/bootstrap.sh | sudo GHCR_OWNER=<owner> bash
#
# What it does:
#   1. apt update/upgrade, base packages, unattended-upgrades for the OS.
#   2. Docker Engine + compose plugin from get.docker.com; adds $TINCAN_USER to the docker group.
#   3. Tailscale; `tailscale up --ssh` (prints the auth URL for you to open).
#   4. /data (recordings, db) and /opt/tincan (compose.yaml, .env, scripts).
#   5. systemd: tincan.service (compose up on boot), tincan-update.timer (OTA every 10 min),
#      tincan-backup.timer (nightly).
# It does NOT fill in .env or rclone.conf: that's you, then `systemctl start tincan`.
set -euo pipefail

[[ $(id -u) -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }

TINCAN_USER=${TINCAN_USER:-${SUDO_USER:-pi}}
TINCAN_DIR=/opt/tincan
DATA_DIR=${TINCAN_DATA_DIR:-/data}
GHCR_OWNER=${GHCR_OWNER:-}
# Where the deploy/ files come from: this checkout if we're in one, else the main branch.
SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)
RAW_BASE=${RAW_BASE:-https://raw.githubusercontent.com/${GHCR_OWNER:-hmbootin}/pi-phone/main/deploy}
export DEBIAN_FRONTEND=noninteractive

log() { printf '\n==> %s\n' "$*"; }

# Fetch a deploy/ file from the checkout or GitHub into $2.
fetch() {
  local rel=$1 dst=$2
  if [[ -n "$SRC_DIR" && -f "$SRC_DIR/$rel" ]]; then
    install -m "${3:-0644}" "$SRC_DIR/$rel" "$dst"
  else
    curl -fsSL "$RAW_BASE/$rel" -o "$dst"
    chmod "${3:-0644}" "$dst"
  fi
}

# ------------------------------------------------------------------ 1. OS
log "OS packages"
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q --no-install-recommends \
  ca-certificates curl gnupg rsync git jq sqlite3 unattended-upgrades apt-listchanges
# Security updates on their own; Docker and Tailscale ship their own repos and update with apt.
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT
# Never auto-reboot: a reboot mid-call would be rude. Kernel updates apply on the next manual reboot.
sed -i 's|^//Unattended-Upgrade::Automatic-Reboot "false";|Unattended-Upgrade::Automatic-Reboot "false";|' \
  /etc/apt/apt.conf.d/50unattended-upgrades || true

# ------------------------------------------------------------------ 2. Docker
if ! command -v docker >/dev/null; then
  log "Docker (get.docker.com)"
  curl -fsSL https://get.docker.com | sh
else
  log "Docker already installed: $(docker --version)"
fi
docker compose version >/dev/null 2>&1 || apt-get install -y -q docker-compose-plugin
systemctl enable --now docker
if id "$TINCAN_USER" >/dev/null 2>&1 && ! id -nG "$TINCAN_USER" | grep -qw docker; then
  usermod -aG docker "$TINCAN_USER"
  log "added $TINCAN_USER to the docker group (log out and back in for it to apply)"
fi
# Keep container logs from eating the SD card even if a compose file forgets logging: options.
if [[ ! -f /etc/docker/daemon.json ]]; then
  cat >/etc/docker/daemon.json <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "5" } }
JSON
  systemctl restart docker
fi

# ------------------------------------------------------------------ 3. Tailscale
if ! command -v tailscale >/dev/null; then
  log "Tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
fi
systemctl enable --now tailscaled
if ! tailscale status >/dev/null 2>&1; then
  log "Tailscale login. Open the URL below on any device signed in to your tailnet."
  log "(--ssh lets you 'ssh tincan' with no keys to manage; see docs/remote-dev.md)"
  tailscale up --ssh --hostname "${TAILSCALE_HOSTNAME:-tincan}"
else
  log "Tailscale already up as $(tailscale status --json | jq -r .Self.DNSName)"
  tailscale set --ssh=true >/dev/null 2>&1 || true
fi

# ------------------------------------------------------------------ 4. Directories
log "$DATA_DIR and $TINCAN_DIR"
# /data is bind-mounted into every container; the asterisk and backend images run as uid 2000
# ("asterisk"/"tincan"); keeping it group-writable by a host group with that gid lets both the
# containers and a human on the host read recordings. 2000 is deliberately not a login user.
getent group tincan >/dev/null || groupadd -g 2000 tincan
mkdir -p "$DATA_DIR"/{recordings,prompts,backup,asterisk/recording}
chown -R 2000:tincan "$DATA_DIR"
chmod 2775 "$DATA_DIR" "$DATA_DIR"/{recordings,prompts,backup,asterisk,asterisk/recording}
usermod -aG tincan "$TINCAN_USER" 2>/dev/null || true

mkdir -p "$TINCAN_DIR"
fetch compose.yaml "$TINCAN_DIR/compose.yaml"
fetch update.sh "$TINCAN_DIR/update.sh" 0755
fetch backup.sh "$TINCAN_DIR/backup.sh" 0755
fetch rclone.conf.example "$TINCAN_DIR/rclone.conf.example"
if [[ ! -f "$TINCAN_DIR/.env" ]]; then
  fetch .env.example "$TINCAN_DIR/.env" 0600
  # Pre-fill what we can so a fresh Pi comes up with unique secrets instead of "change-me".
  [[ -n "$GHCR_OWNER" ]] && sed -i "s|^GHCR_OWNER=.*|GHCR_OWNER=$GHCR_OWNER|" "$TINCAN_DIR/.env"
  for key in ARI_PASSWORD PHONE_SIP_PASSWORD TINCAN_SECRET_KEY; do
    sed -i "s|^$key=.*|$key=$(openssl rand -hex 24)|" "$TINCAN_DIR/.env"
  done
  sed -i "s|^TINCAN_DATA_DIR=.*|TINCAN_DATA_DIR=$DATA_DIR|" "$TINCAN_DIR/.env"
  sed -i "s|^TZ=.*|TZ=$(cat /etc/timezone 2>/dev/null || echo UTC)|" "$TINCAN_DIR/.env"
  log "wrote $TINCAN_DIR/.env with fresh secrets. EDIT IT: TINCAN_PARENT_PASSWORD, TRUNK_*"
else
  log "$TINCAN_DIR/.env exists; left untouched"
fi
[[ -f "$TINCAN_DIR/channel" ]] || echo stable >"$TINCAN_DIR/channel"
chown -R "$TINCAN_USER:$TINCAN_USER" "$TINCAN_DIR"
chmod 0600 "$TINCAN_DIR/.env"

# ------------------------------------------------------------------ 5. systemd
log "systemd units"
for unit in tincan.service tincan-update.service tincan-update.timer tincan-backup.service tincan-backup.timer; do
  fetch "systemd/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable tincan.service tincan-update.timer tincan-backup.timer
systemctl start tincan-update.timer tincan-backup.timer
# tincan.service is enabled for boot but not started: .env isn't filled in yet.

# ------------------------------------------------------------------ done
cat <<DONE

Bootstrap complete. Next:

  1. sudo nano $TINCAN_DIR/.env          # parent password, trunk credentials, GHCR_OWNER
  2. sudo cp $TINCAN_DIR/rclone.conf.example $TINCAN_DIR/rclone.conf && sudo nano \$_   # backups
     sudo chmod 600 $TINCAN_DIR/rclone.conf
  3. sudo systemctl start tincan          # first pull takes a few minutes on a Pi
  4. docker compose -f $TINCAN_DIR/compose.yaml logs -f

Updates: tincan-update.timer checks GitHub every 10 min and follows \$(cat $TINCAN_DIR/channel).
Backups: tincan-backup.timer runs nightly. Test now: sudo $TINCAN_DIR/backup.sh
Tailscale: ssh ${TINCAN_USER}@$(hostname) from any device on your tailnet.

USB SSD (recommended; SD cards die): format it ext4, add to /etc/fstab mounted at $DATA_DIR
with 'nofail,x-systemd.device-timeout=10', move the contents over, re-run this script.
DONE
