#!/usr/bin/env bash
# Tin Can Asterisk container entrypoint.
#
# 1. Render every /etc/asterisk/*.conf.tmpl into the matching *.conf with envsubst, using a
#    FIXED variable list so dialplan variables like ${EXTEN} and ${CALLERID(num)} survive.
# 2. Pick the trunk template for ${TRUNK_PROVIDER} (voipms|telnyx|twilio|none) and render it to
#    pjsip_trunk.conf, which pjsip.conf #includes.
# 3. Make sure /data/recordings and /data/prompts exist and belong to the asterisk user.
# 4. exec asterisk in the foreground.
#
# The list in TEMPLATE_VARS is the contract with asterisk/etc/README.md and with the CI check
# in .github/workflows/ci.yml, which fails if a template references a ${VAR} not listed here.
set -euo pipefail

ETC=/etc/asterisk
ASTERISK_USER=${ASTERISK_USER:-asterisk}
TRUNK_PROVIDER=${TRUNK_PROVIDER:-none}

# Variables that templates are allowed to reference. Anything else is left untouched.
TEMPLATE_VARS='$ARI_USER $ARI_PASSWORD $PHONE_SIP_PASSWORD $EXTERNAL_IP $LOCAL_NET $TRUNK_PROVIDER $TRUNK_HOST $TRUNK_USERNAME $TRUNK_PASSWORD $TRUNK_DID'

log() { printf '[entrypoint] %s\n' "$*" >&2; }

require() {
  local name=$1
  if [[ -z "${!name:-}" ]]; then
    log "ERROR: $name is not set"
    exit 1
  fi
}

# Credentials the phone service and the backend use; Asterisk is useless without them.
require ARI_USER
require ARI_PASSWORD
require PHONE_SIP_PASSWORD

case "$TRUNK_PROVIDER" in
  voipms|telnyx|twilio)
    require TRUNK_HOST
    require TRUNK_USERNAME
    require TRUNK_PASSWORD
    require TRUNK_DID
    ;;
  none)
    # Unset trunk vars must still expand to *something* so pjsip.conf stays parseable.
    : "${TRUNK_HOST:=}" "${TRUNK_USERNAME:=}" "${TRUNK_PASSWORD:=}" "${TRUNK_DID:=}"
    export TRUNK_HOST TRUNK_USERNAME TRUNK_PASSWORD TRUNK_DID
    ;;
  *)
    log "ERROR: TRUNK_PROVIDER must be voipms, telnyx, twilio or none (got '$TRUNK_PROVIDER')"
    exit 1
    ;;
esac
export TRUNK_PROVIDER

render() {
  local src=$1 dst=$2
  envsubst "$TEMPLATE_VARS" <"$src" >"$dst.tmp"
  mv "$dst.tmp" "$dst"
  chmod 0640 "$dst"
  log "rendered $(basename "$src") -> $(basename "$dst")"
}

# Generic templates: foo.conf.tmpl -> foo.conf. The trunk templates are handled separately.
shopt -s nullglob
for tmpl in "$ETC"/*.conf.tmpl; do
  case "$(basename "$tmpl")" in
    pjsip_trunk_*.conf.tmpl) continue ;;
  esac
  render "$tmpl" "${tmpl%.tmpl}"
done

# Trunk: exactly one provider template becomes pjsip_trunk.conf.
trunk_tmpl="$ETC/pjsip_trunk_${TRUNK_PROVIDER}.conf.tmpl"
if [[ -f "$trunk_tmpl" ]]; then
  render "$trunk_tmpl" "$ETC/pjsip_trunk.conf"
else
  log "WARN: $trunk_tmpl not found; writing an empty pjsip_trunk.conf"
  : >"$ETC/pjsip_trunk.conf"
fi

# Data directories. /data is a bind mount from the host; it may be fresh or owned by root.
# /data/asterisk is astspooldir (asterisk.conf), so ARI recordings land in /data/asterisk/recording;
# /data/recordings and /data/prompts are the backend's. All are backed up by deploy/backup.sh.
for d in /data/recordings /data/prompts /data/asterisk/recording /data/asterisk/monitor /data/asterisk/tmp; do
  mkdir -p "$d"
done
if [[ "$(id -u)" -eq 0 ]]; then
  chown -R "$ASTERISK_USER:$ASTERISK_USER" /data/recordings /data/prompts /data/asterisk "$ETC" \
    /var/run/asterisk /var/log/asterisk /var/spool/asterisk /var/lib/asterisk
  RUN_AS=(-U "$ASTERISK_USER" -G "$ASTERISK_USER")
else
  RUN_AS=()
fi

log "starting asterisk (trunk provider: $TRUNK_PROVIDER)"
# -f foreground, -p high priority off (Pi), -vvv for logs, -c would want a tty so we use -f.
exec asterisk -f "${RUN_AS[@]}" -vvv "$@"
