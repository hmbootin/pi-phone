#!/usr/bin/env bash
# Laptop registration test for the phone service.
#
# Starts Asterisk and the phone container (baresip, sine-wave audio, no sound card) on one
# compose network, waits for Asterisk's `pjsip show endpoints` to show the phone contact as
# Avail, checks ctrl_tcp answers a `reginfo`, and tears everything down.
#
#   phone/test-register.sh              # repo Asterisk image: docker build -t tincan-asterisk:phone-test asterisk
#   phone/test-register.sh --stock      # stock andrius/asterisk:20 + phone/test/asterisk-stock/pjsip.conf
#   KEEP=1 phone/test-register.sh       # leave the rig running for poking (down with: $0 --down)
#   ASTERISK_IMAGE=... phone/test-register.sh
#
# Exit 0 = registered. Exit 1 = not registered within the timeout (logs printed). Exit 2 = setup.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
timeout=${TIMEOUT:-45}
compose=(docker compose -f "$here/compose.test.yaml")
mode=repo

for arg in "$@"; do
  case "$arg" in
    --stock) compose+=(-f "$here/compose.test.stock.yaml"); mode=stock ;;
    --down) "${compose[@]}" -f "$here/compose.test.stock.yaml" down -v --remove-orphans; exit 0 ;;
    *) echo "usage: $0 [--stock] [--down]" >&2; exit 2 ;;
  esac
done

cleanup() {
  if [[ "${KEEP:-0}" == 1 ]]; then
    echo "KEEP=1: rig left running. phone/ctl.sh reginfo; $0 --down to stop." >&2
  else
    "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "$mode" == repo ]]; then
  img=${ASTERISK_IMAGE:-tincan-asterisk:phone-test}
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "ERROR: Asterisk image '$img' not found. Build it with" >&2
    echo "  docker build -t tincan-asterisk:phone-test asterisk" >&2
    echo "or run with --stock to use a stock Asterisk 20 image." >&2
    exit 2
  fi
fi

echo "== starting rig ($mode asterisk)"
"${compose[@]}" up --build -d --quiet-pull --wait --wait-timeout "$timeout" || {
  echo "ERROR: containers did not come up healthy" >&2
  "${compose[@]}" ps
  "${compose[@]}" logs --no-color
  exit 1
}

echo "== waiting up to ${timeout}s for Asterisk to see the phone contact as Avail"
deadline=$((SECONDS + timeout))
registered=0
while (( SECONDS < deadline )); do
  if out=$("${compose[@]}" exec -T asterisk asterisk -rx "pjsip show endpoints" 2>/dev/null) \
     && grep -Eq 'Contact: +phone/sip:phone[^ ]*@.*Avail' <<<"$out"; then
    registered=1
    break
  fi
  sleep 2
done

echo "== pjsip show endpoints"
"${compose[@]}" exec -T asterisk asterisk -rx "pjsip show endpoints" || true

echo "== ctrl_tcp reginfo (published on 127.0.0.1:4444)"
reg=$(PHONE_CTRL_HOST=127.0.0.1 PHONE_CTRL_PORT=4444 PHONE_CTRL_WAIT=2 "$here/ctl.sh" reginfo 2>/dev/null || true)
printf '%s\n' "$reg"

if (( registered )) && grep -q '"response":true,"ok":true' <<<"$reg"; then
  echo "== PASS: phone registered to Asterisk ($mode) and ctrl_tcp answers"
  exit 0
fi

echo "== FAIL: registered=$registered, ctrl_tcp ok=$(grep -c '"ok":true' <<<"$reg" || true)" >&2
"${compose[@]}" logs --no-color --tail 60 phone asterisk
exit 1
