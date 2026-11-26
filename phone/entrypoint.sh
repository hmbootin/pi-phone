#!/usr/bin/env bash
# Tin Can phone (baresip) container entrypoint.
#
# 1. Validate env (PHONE_SIP_PASSWORD is required; everything else has a default).
# 2. Render /etc/baresip/config.tmpl and accounts.tmpl -> config, accounts with envsubst over a
#    FIXED variable list, same pattern as asterisk/entrypoint.sh.
# 3. exec baresip in the foreground, reading /etc/baresip.
#
# TEMPLATE_VARS is the contract with the two templates and README.md "Environment".
set -euo pipefail

ETC=/etc/baresip

# Defaults. See README.md for what each one means.
ASTERISK_HOST=${ASTERISK_HOST:-127.0.0.1}
PHONE_AUDIO_MODULE=${PHONE_AUDIO_MODULE:-alsa}
PHONE_AUDIO_DEVICE=${PHONE_AUDIO_DEVICE:-plughw:1,0}
# Device sample rate. 8000 on the Pi (plughw resamples); 48000 for the ausine test module.
PHONE_AUDIO_SRATE=${PHONE_AUDIO_SRATE:-8000}
PHONE_CTRL_PORT=${PHONE_CTRL_PORT:-4444}
# 0.0.0.0 because the backend lives on Docker's bridge network and reaches us through
# host.docker.internal; with network_mode: host that also exposes the (unauthenticated) control
# port to the LAN. Set 127.0.0.1 if the backend ever moves to host networking too.
PHONE_CTRL_BIND=${PHONE_CTRL_BIND:-0.0.0.0}
# Asterisk owns 5060 on the same host; we take 5062 on every interface (see config.tmpl).
PHONE_SIP_LISTEN=${PHONE_SIP_LISTEN:-0.0.0.0:5062}
export ASTERISK_HOST PHONE_AUDIO_MODULE PHONE_AUDIO_DEVICE PHONE_AUDIO_SRATE PHONE_CTRL_PORT PHONE_CTRL_BIND PHONE_SIP_LISTEN

TEMPLATE_VARS='$ASTERISK_HOST $PHONE_SIP_PASSWORD $PHONE_AUDIO_MODULE $PHONE_AUDIO_DEVICE $PHONE_AUDIO_SRATE $PHONE_CTRL_BIND $PHONE_CTRL_PORT $PHONE_SIP_LISTEN'

log() { printf '[entrypoint] %s\n' "$*" >&2; }

if [[ -z "${PHONE_SIP_PASSWORD:-}" ]]; then
  log "ERROR: PHONE_SIP_PASSWORD is not set"
  exit 1
fi
# The accounts line is "<sip:...>;auth_pass=VALUE;..." so these characters would corrupt it.
if [[ "$PHONE_SIP_PASSWORD" == *[\;\>\<\"\ ]* ]]; then
  log "ERROR: PHONE_SIP_PASSWORD must not contain ; < > \" or spaces (use openssl rand -hex 24)"
  exit 1
fi
case "$PHONE_CTRL_PORT" in
  ''|*[!0-9]*) log "ERROR: PHONE_CTRL_PORT must be a number (got '$PHONE_CTRL_PORT')"; exit 1 ;;
esac
case "$PHONE_AUDIO_SRATE" in
  ''|*[!0-9]*) log "ERROR: PHONE_AUDIO_SRATE must be a number (got '$PHONE_AUDIO_SRATE')"; exit 1 ;;
esac
if [[ ! -f "/usr/lib/baresip/modules/${PHONE_AUDIO_MODULE}.so" ]]; then
  log "ERROR: PHONE_AUDIO_MODULE='$PHONE_AUDIO_MODULE' is not a baresip module (see /usr/lib/baresip/modules)"
  exit 1
fi
export PHONE_SIP_PASSWORD

render() {
  local src=$1 dst=$2
  envsubst "$TEMPLATE_VARS" <"$src" >"$dst.tmp"
  mv "$dst.tmp" "$dst"
  chmod 0600 "$dst"
  log "rendered $(basename "$src") -> $(basename "$dst")"
}

render "$ETC/config.tmpl" "$ETC/config"
render "$ETC/accounts.tmpl" "$ETC/accounts"

if [[ "$PHONE_AUDIO_MODULE" == "alsa" && ! -d /dev/snd ]]; then
  log "WARN: /dev/snd is not present in the container; alsa will fail to open '$PHONE_AUDIO_DEVICE' on the first call"
fi

log "starting baresip (asterisk: $ASTERISK_HOST, audio: $PHONE_AUDIO_MODULE,$PHONE_AUDIO_DEVICE @ ${PHONE_AUDIO_SRATE} Hz, ctrl_tcp: $PHONE_CTRL_BIND:$PHONE_CTRL_PORT)"
# -f config dir, -v verbose logging. No -d (daemon) so the container's PID 1 child is baresip.
exec baresip -f "$ETC" -v "$@"
