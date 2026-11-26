#!/usr/bin/env bash
# Send one command to baresip's ctrl_tcp by hand and print what comes back.
#
#   phone/ctl.sh reginfo
#   phone/ctl.sh dial sip:2@127.0.0.1
#   phone/ctl.sh listcalls
#   PHONE_CTRL_HOST=tincan phone/ctl.sh hangup
#
# Frames {"command":..,"params":..,"token":..} as a netstring ("<len>:<json>,") and leaves the
# socket open for PHONE_CTRL_WAIT seconds (default 2) so the response and any events arrive.
# Needs nc (any flavour: macOS, GNU, busybox).
#
# WARNING: ctrl_tcp keeps ONE client. Running this against a live Pi disconnects the backend's
# control connection until it reconnects. Fine for debugging, not for a cron job.
set -euo pipefail

host=${PHONE_CTRL_HOST:-127.0.0.1}
port=${PHONE_CTRL_PORT:-4444}
wait=${PHONE_CTRL_WAIT:-2}

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <command> [params]  (e.g. $0 dial sip:2@127.0.0.1)" >&2
  exit 2
fi
cmd=$1
params=${2:-}
token="ctl-$$"

# Minimal JSON string escaping for the two values (backslash and double quote).
esc() { local s=${1//\\/\\\\}; printf '%s' "${s//\"/\\\"}"; }

if [[ -n "$params" ]]; then
  json=$(printf '{"command":"%s","params":"%s","token":"%s"}' "$(esc "$cmd")" "$(esc "$params")" "$token")
else
  json=$(printf '{"command":"%s","token":"%s"}' "$(esc "$cmd")" "$token")
fi
frame=$(printf '%d:%s,' "${#json}" "$json")

echo ">>> $frame" >&2
{ printf '%s' "$frame"; sleep "$wait"; } | nc "$host" "$port"
echo
