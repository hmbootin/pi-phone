#!/usr/bin/env bash
# Smoke test for the tincan-asterisk image. Used by .github/workflows/asterisk-image.yml and by
# hand after `docker build -t tincan-asterisk:ci-test asterisk` (see asterisk/etc/README.md).
#
# Starts the image with the minimum env from deploy/.env.example (no trunk), waits for the
# HEALTHCHECK, then proves the things the Pi weekend depends on:
#   - the entrypoint rendered the templates and Asterisk came up
#   - every `load =>` in modules.conf names a module that exists in the image
#   - nothing failed to load; chan_pjsip and res_ari are Running
#   - the `phone` PJSIP endpoint and the from-phone -> Stasis(tincan,...) dialplan exist
#   - ARI answers over HTTP with the rendered credentials and rejects a wrong password
#
# Usage: asterisk/smoke-test.sh [image]        (default tincan-asterisk:ci-test)
# Needs docker and curl on the host. ARI is published on 127.0.0.1:8088 for the duration of the
# test (host networking is Linux-only, so a port mapping works on macOS and CI alike).
set -euo pipefail

IMAGE=${1:-tincan-asterisk:ci-test}
NAME=${SMOKE_CONTAINER:-tincan-asterisk-smoke}
ARI_PORT=${SMOKE_ARI_PORT:-8088}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

FAILED=0
pass() { printf 'ok:   %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; FAILED=1; }

cleanup() {
  if [[ "$FAILED" -ne 0 ]]; then
    echo "----- container log (tail) -----" >&2
    docker logs --tail 80 "$NAME" >&2 || true
  fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "127.0.0.1:${ARI_PORT}:8088" \
  -e ARI_USER=smoke -e ARI_PASSWORD=smoke-pass \
  -e PHONE_SIP_PASSWORD=smoke-sip -e TRUNK_PROVIDER=none \
  "$IMAGE" >/dev/null

# Wait for the Dockerfile HEALTHCHECK (asterisk -rx "core show uptime"); start-period is 20s.
status=starting
for _ in $(seq 1 60); do
  status=$(docker inspect -f '{{.State.Health.Status}}' "$NAME" 2>/dev/null || echo missing)
  case "$status" in
    healthy|unhealthy|missing) break ;;
  esac
  sleep 2
done
if [[ "$status" != healthy ]]; then
  fail "container never became healthy (status: $status)"
  exit 1
fi
pass "container healthy"

rx() { docker exec "$NAME" asterisk -rx "$1"; }

# 1. the entrypoint rendered the templates
for f in ari.conf pjsip.conf pjsip_trunk.conf; do
  if docker exec "$NAME" test -f "/etc/asterisk/$f"; then
    pass "rendered /etc/asterisk/$f"
  else
    fail "/etc/asterisk/$f not rendered"
  fi
done
if docker exec "$NAME" grep -q '^\[smoke\]' /etc/asterisk/ari.conf; then
  pass "ari.conf has the [ARI_USER] section"
else
  fail "ari.conf is missing the [smoke] user section"
fi

# 2. modules.conf vs the image: every `load =>` must exist on disk
missing=0
while read -r mod; do
  if ! docker exec "$NAME" test -f "/usr/lib/asterisk/modules/$mod"; then
    fail "modules.conf loads $mod but it is not in the image"
    missing=1
  fi
done < <(sed -n 's/^load *=> *\([^ ;]*\.so\).*$/\1/p' "$HERE/etc/modules.conf")
[[ $missing -eq 0 ]] && pass "every load => in modules.conf exists in /usr/lib/asterisk/modules"

# 3. nothing failed to load, and the key modules are Running
# ("Could not load <x> config; using defaults" NOTICEs for stasis.conf/features.conf/udptl.conf
# are benign and deliberately not matched.)
load_err='Error loading module|Module load failed|declined to load|Failed to load'
log=$(docker logs "$NAME" 2>&1)
if grep -qE "$load_err" <<<"$log"; then
  fail "module load errors in the log:"
  grep -E "$load_err" <<<"$log" >&2
else
  pass "no module load errors in the log"
fi
pjsip=$(rx "module show like pjsip")
if grep -qE '^chan_pjsip\.so .*Running' <<<"$pjsip"; then pass "chan_pjsip.so Running"; else fail "chan_pjsip.so not Running"; fi
ari=$(rx "module show like res_ari")
if grep -qE '^res_ari\.so .*Running' <<<"$ari"; then pass "res_ari.so Running"; else fail "res_ari.so not Running"; fi
notrunning=$(rx "module show" | grep -E 'Not Running' || true)
if [[ -n "$notrunning" ]]; then
  fail "modules Not Running:"
  echo "$notrunning" >&2
else
  pass "no module is 'Not Running'"
fi

# 4. the phone endpoint and the dialplan
endpoints=$(rx "pjsip show endpoints")
if grep -qE 'Endpoint: +phone' <<<"$endpoints"; then
  pass "pjsip show endpoints lists phone"
else
  fail "phone endpoint missing"
  echo "$endpoints" >&2
fi
# `dialplan show` prints the app name as written, i.e. the unexpanded ${TINCAN_APP} global.
dialplan=$(rx "dialplan show from-phone")
if grep -qE 'Stasis\((tincan|\$\{TINCAN_APP\}),dial,\$\{EXTEN\}\)' <<<"$dialplan"; then
  pass "from-phone enters Stasis(tincan,dial,...)"
else
  fail "from-phone has no Stasis line"
  echo "$dialplan" >&2
fi

# 5. ARI over HTTP with the rendered credentials
if info=$(curl -fsS -u smoke:smoke-pass "http://127.0.0.1:${ARI_PORT}/ari/asterisk/info" 2>&1); then
  pass "GET /ari/asterisk/info: $(printf '%s' "$info" | head -c 200)"
else
  fail "GET /ari/asterisk/info failed: $info"
fi
if curl -fsS -u smoke:wrong "http://127.0.0.1:${ARI_PORT}/ari/asterisk/info" >/dev/null 2>&1; then
  fail "ARI accepted a wrong password"
else
  pass "ARI rejects a wrong password"
fi

echo "----- module show like pjsip -----"; echo "$pjsip"
echo "----- module show like res_ari -----"; echo "$ari"
echo "----- pjsip show endpoints -----"; echo "$endpoints"
echo "----- dialplan show from-phone -----"; echo "$dialplan"

if [[ "$FAILED" -ne 0 ]]; then
  echo "SMOKE TEST FAILED ($IMAGE)" >&2
  exit 1
fi
echo "SMOKE TEST PASSED ($IMAGE)"
