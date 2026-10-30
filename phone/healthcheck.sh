#!/usr/bin/env bash
# Healthy when baresip's ctrl_tcp socket is listening on PHONE_CTRL_PORT.
#
# Deliberately does NOT connect: ctrl_tcp (baresip 1.1.0, modules/ctrl_tcp/ctrl_tcp.c
# tcp_conn_handler) keeps exactly one client and drops the previous one whenever a new connection
# arrives, so a probing healthcheck would disconnect the backend every interval. Instead we read
# the kernel's socket table: a LISTEN (state 0A) entry for the port on any address.
set -euo pipefail

port=${PHONE_CTRL_PORT:-4444}
hex=$(printf '%04X' "$port")

# /proc/net/tcp columns: sl local_address rem_address st ...; local_address is HEXIP:HEXPORT.
for table in /proc/net/tcp /proc/net/tcp6; do
  [[ -r "$table" ]] || continue
  if awk -v p=":$hex" '$2 ~ p"$" && $4 == "0A" { found = 1 } END { exit found ? 0 : 1 }' "$table"; then
    exit 0
  fi
done

echo "ctrl_tcp port $port is not listening" >&2
exit 1
