# phone: the baresip container

The `phone` Compose service is the toddler's handset as a SIP phone. It wraps
[baresip](https://github.com/baresip/baresip) **v1.1.0** (Debian trixie's `baresip-core`
package, linux/arm64 and amd64), opens the handset's USB audio adapter through ALSA, registers to
the Asterisk container as PJSIP endpoint `phone` (see `asterisk/etc/pjsip.conf.tmpl`), and takes
orders from the backend over baresip's `ctrl_tcp` module: a TCP socket speaking netstring-framed
JSON. The backend never touches audio; it tells this container to dial, accept and hang up, and
reads call events back.

Why a 2021 baresip: every pinnable distro package is 1.x (bookworm and Ubuntu noble ship 1.0.0,
trixie 1.1.0; Alpine stable has none, edge/testing has 4.10). The ctrl_tcp message shape has not
changed since 1.x, so a later source build of 3.x/4.x is a `Dockerfile`-only change; the protocol
below was verified against the v1.1.0 source (`modules/ctrl_tcp/ctrl_tcp.c`, `src/event.c`,
`modules/menu/*.c`) and by running it (see "Verified").

| File | Purpose |
|------|---------|
| `Dockerfile` | `debian:trixie-slim` + `baresip-core`, `alsa-utils`, `gettext-base`, `tini`. Runs as uid 2001 with the `audio` group. |
| `entrypoint.sh` | Renders `etc/config.tmpl` and `etc/accounts.tmpl` from env with a fixed `envsubst` list, then `exec baresip -f /etc/baresip`. |
| `healthcheck.sh` | Healthy when the ctrl_tcp port is in LISTEN (read from `/proc/net/tcp`; it must not connect, see below). |
| `etc/config.tmpl` | baresip `config`: SIP on `0.0.0.0:5062`, G.711 only, no video, `menu` + `ctrl_tcp` modules. |
| `etc/accounts.tmpl` | One account: `sip:phone@${ASTERISK_HOST}`, `regint=60`, `answermode=manual`, PCMU/PCMA. |
| `ctl.sh` | Send one command by hand and print the response (`nc` + netstring framing). |
| `compose.test.yaml`, `compose.test.stock.yaml`, `test-register.sh`, `test/` | Laptop registration test, below. |

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `PHONE_SIP_PASSWORD` | required | Password for the `phone` endpoint; the same value goes to the asterisk service. Must not contain `;` `<` `>` `"` or spaces (`openssl rand -hex 24`). |
| `ASTERISK_HOST` | `127.0.0.1` | Where to register. `127.0.0.1` on the Pi (both containers on host networking); the compose service name in the laptop rig. |
| `PHONE_AUDIO_MODULE` | `alsa` | baresip audio driver module for player, source and alert. `ausine` for a box with no sound card (a 440 Hz tone as the mic, no player). Must exist in `/usr/lib/baresip/modules`. |
| `PHONE_AUDIO_DEVICE` | `plughw:1,0` | Device string for that module: the ALSA name of the USB adapter (`aplay -l`), or the tone frequency for `ausine`. |
| `PHONE_AUDIO_SRATE` | `8000` | Device sample rate. `plughw` resamples to 8 kHz on the Pi. `ausine` only runs at `48000`; baresip resamples to the 8 kHz codec. |
| `PHONE_CTRL_PORT` | `4444` | ctrl_tcp TCP port. |
| `PHONE_CTRL_BIND` | `0.0.0.0` | ctrl_tcp bind address. `0.0.0.0` because the backend runs on Docker's bridge network and reaches the phone through `host.docker.internal`. With host networking that also exposes the port, which has **no authentication**, to the LAN: any host that can reach the Pi can make the phone dial. Fine on a home LAN behind a router; set `127.0.0.1` if the backend ever moves to host networking. |
| `PHONE_SIP_LISTEN` | `0.0.0.0:5062` | SIP listen address. Asterisk owns 5060 on the same host. |

Only these variables are substituted into the templates (`TEMPLATE_VARS` in `entrypoint.sh`;
CI checks the templates reference nothing else).

## The ctrl_tcp protocol (baresip 1.1.0)

**Transport.** One TCP connection to `PHONE_CTRL_HOST:PHONE_CTRL_PORT`. Every message in both
directions is one JSON object wrapped in a [netstring](https://cr.yp.to/proto/netstrings.txt):
`<decimal byte length>:<json>,` — for example `38:{"command":"help","token":"ctl-43018"},`.
Messages are concatenated on the stream with no other separator; parse by length, not by
newline. Max frame 2 KB on the response side (`mbuf_alloc(2048)` in the module).

**Exactly one client.** `tcp_conn_handler` in `ctrl_tcp.c` drops the current connection whenever
a new one arrives. The backend must hold one long-lived connection and reconnect on EOF; any
hand `nc`/`ctl.sh` session against a live Pi kicks the backend off until it reconnects. This
is also why `healthcheck.sh` only inspects `/proc/net/tcp`.

**Command** (client to baresip):

```json
{"command": "dial", "params": "sip:2@127.0.0.1", "token": "any-string"}
```

`command` is required, `params` optional (joined to the command with a space and handed to
baresip's long-command dispatcher), `token` optional and echoed back. Commands are the long
names from `help`; the ones Tin Can uses:

| Command | `params` | What it does | Notes |
|---------|----------|--------------|-------|
| `dial` | SIP URI or number | Start an outgoing call | Response `data` is `"call id: <id>\n"`; the same `id` appears in every later event for that call. On the Pi dial `sip:<digit>@127.0.0.1`. |
| `accept` | — | Answer the ringing incoming call | `ok:false` with `"no active call"` if nothing is ringing. |
| `hangup` | — | Hang up the current call | Same error when idle. Emits `CALL_CLOSED` with `"param":"Connection reset by user"`. |
| `sndcode` | DTMF digit(s) | Send DTMF on the established call (RFC 4733) | Emits `CALL_DTMF_START` with the digit in `param` (in-call only). |
| `listcalls` | — | Text list of calls, e.g. `> [line 1, id b7b6…]  0:00:06  ESTABLISHED  sip:2@asterisk` | Good for resync after a reconnect. |
| `reginfo` | — | Registration status text, `OK` when registered, `ERR` otherwise | The text contains ANSI colour escapes (`\u001B[32m`). |
| `help` | — | All commands | |

**Response** (baresip to client), one per command, after any events the command triggered
synchronously:

```json
{"response": true, "ok": true, "data": "call id: b7b696da9070a9e6\n", "token": "any-string"}
```

`ok` is `false` when the command handler returned an error; `data` then holds the handler's
message (`"no active call\n"`, `"command not found (nosuch)\n"`) or `strerror` of the code.

**Event** (baresip to client, unsolicited, whenever the connection is open):

```json
{"event": true, "type": "CALL_INCOMING", "class": "call",
 "accountaor": "sip:phone@127.0.0.1", "direction": "incoming",
 "peeruri": "sip:anonymous@anonymous.invalid", "peerdisplayname": "Anonymous",
 "id": "8ed5b35c-5d0f-4326-a8a1-eab019aca8a8", "remoteaudiodir": "sendrecv",
 "param": "sip:anonymous@anonymous.invalid"}
```

Always present: `event`, `type`, `class`, `accountaor`. Present when a call is involved:
`direction` (`incoming`/`outgoing`), `peeruri`, `id`, `remoteaudiodir`; `peerdisplayname` only
when the peer sent one. `param` carries type-specific text. `CALL_RTCP` adds an `rtcp_stats`
object. `type` values from `src/event.c` (class in parentheses):

| `type` | When | `param` |
|--------|------|---------|
| `REGISTERING`, `REGISTER_OK`, `REGISTER_FAIL`, `UNREGISTERING` (`register`) | registration state | error text on failure |
| `CALL_INCOMING` (`call`) | INVITE arrived, phone is "ringing" | peer URI |
| `CALL_RINGING`, `CALL_PROGRESS` (`call`) | outgoing call got 180/183 | |
| `CALL_ANSWERED` (`call`) | outgoing call got 200 (before media) | peer URI |
| `CALL_ESTABLISHED` (`call`) | media set up, both directions | peer URI |
| `CALL_CLOSED` (`call`) | call ended, any reason | reason: `"Connection reset by user"` (our hangup), SIP status text, or an errno string |
| `CALL_DTMF_START`, `CALL_DTMF_END` (`call`) | DTMF sent or received | the digit |
| `CALL_RTCP` (`call`) | periodic stats | `"audio"` + `rtcp_stats` |
| `CALL_LOCAL_SDP`, `CALL_REMOTE_SDP`, `CALL_RTPESTAB` (`other`) | SDP offer/answer, first RTP | `offer`/`answer`/`audio` |
| `SHUTDOWN`, `EXIT` (`application`) | baresip stopping | |
| `MWI_NOTIFY`, `TRANSFER`, `TRANSFER_FAILED`, `CALL_MENC`, `VU_TX_REPORT`, `VU_RX_REPORT`, `AUDIO_ERROR`, `MODULE`, `CUSTOM` | not used by Tin Can | |

A client should ignore unknown `type`s and `class`es.

SIP MESSAGE bodies arrive as a third shape, `{"message": true, ...}`; Tin Can does not use it.

### Observed sequences

Outgoing, dialled from the backend, far end answers, we hang up (laptop rig, Asterisk `Echo()`):

```
> {"command":"dial","params":"sip:2@asterisk","token":"t1"}
< {"event":true,"type":"CALL_LOCAL_SDP",...,"param":"offer"}
< {"response":true,"ok":true,"data":"call id: b7b696da9070a9e6\n","token":"t1"}
< {"event":true,"type":"CALL_ANSWERED",...,"id":"b7b696da9070a9e6","param":"sip:2@asterisk"}
< {"event":true,"type":"CALL_REMOTE_SDP",...,"param":"answer"}
< {"event":true,"type":"CALL_ESTABLISHED",...,"param":"sip:2@asterisk"}
< {"event":true,"type":"CALL_RTPESTAB",...,"param":"audio"}
< {"event":true,"type":"CALL_RTCP",...,"rtcp_stats":{"tx":{"sent":251,"lost":0,"jit":1250},"rx":{"sent":250,"lost":0,"jit":1375},"rtt":0}}
> {"command":"hangup","token":"t2"}
< {"event":true,"type":"CALL_CLOSED",...,"param":"Connection reset by user"}
< {"response":true,"ok":true,"data":"","token":"t2"}
```

Incoming (Asterisk `channel originate PJSIP/phone application Echo`), backend accepts, sends a
DTMF 5, hangs up:

```
< {"event":true,"type":"CALL_INCOMING","direction":"incoming","peeruri":"sip:anonymous@anonymous.invalid","id":"8ed5…","param":"sip:anonymous@anonymous.invalid"}
< {"event":true,"type":"CALL_REMOTE_SDP",...,"param":"offer"}
< {"event":true,"type":"CALL_LOCAL_SDP",...,"param":"answer"}
> {"command":"accept","token":"a"}
< {"response":true,"ok":true,"data":"","token":"a"}
< {"event":true,"type":"CALL_ESTABLISHED",...}
< {"event":true,"type":"CALL_RTPESTAB",...,"param":"audio"}
> {"command":"sndcode","params":"5","token":"d"}
< {"response":true,"ok":true,"data":"","token":"d"}
< {"event":true,"type":"CALL_DTMF_START",...,"param":"5"}
> {"command":"hangup","token":"h"}
< {"event":true,"type":"CALL_CLOSED",...,"param":"Connection reset by user"}
< {"response":true,"ok":true,"data":"","token":"h"}
```

Note `CALL_INCOMING` can arrive before the client's `accept` response and that the response to
`dial` comes *after* `CALL_LOCAL_SDP`; match by `token` for responses and by `id` for calls, never
by order. The call `id` for outgoing calls is only in the `dial` response text and later events.

### By hand

```
phone/ctl.sh reginfo                       # 127.0.0.1:4444 (laptop rig publishes it there)
PHONE_CTRL_HOST=tincan phone/ctl.sh listcalls
phone/ctl.sh dial sip:2@127.0.0.1
phone/ctl.sh hangup
```

Raw, with `nc` (macOS `nc` has no `-q`, so keep stdin open with a `sleep`):

```
msg='{"command":"reginfo","token":"x"}'
{ printf '%d:%s,' "${#msg}" "$msg"; sleep 2; } | nc 127.0.0.1 4444
```

Remember each of these disconnects whoever was connected before (the backend, on a live Pi).

## Running it

On the Pi, `deploy/compose.yaml` runs it with `network_mode: host`, `/dev/snd`, `group_add:
audio`, `ASTERISK_HOST=127.0.0.1` and the `PHONE_*` values from `/opt/tincan/.env`. baresip binds
SIP `0.0.0.0:5062/udp`, RTP `20000-20100/udp` and ctrl_tcp `0.0.0.0:4444/tcp` on the host.

Find the USB adapter's ALSA name on the Pi host (`aplay -l`): card 0 is the Pi's own jack, the
CM108 adapter is usually card 1, hence `plughw:1,0`. The same number must be visible inside the
container: `docker compose exec phone aplay -l`.

### Laptop test (no Pi, no sound card)

Docker Desktop on macOS has no real host networking, so the laptop rig puts Asterisk and the
phone on one compose bridge network and sets `ASTERISK_HOST=asterisk`. Audio is the `ausine`
module at 48 kHz (a 440 Hz tone is the "mic"; there is no player, so received audio is dropped,
but RTP flows both ways and the call stays up).

```
docker build -t tincan-asterisk:phone-test asterisk    # the repo image (20-40 min, compiles Asterisk)
phone/test-register.sh                                   # or:
phone/test-register.sh --stock                           # stock andrius/asterisk:20 + phone/test/asterisk-stock/pjsip.conf
```

The script starts both containers, waits up to 45 s for `asterisk -rx "pjsip show endpoints"`
to show the `phone` contact as `Avail`, checks `reginfo` over ctrl_tcp answers `ok:true`, prints
both, and tears down (`KEEP=1` leaves it up; `phone/test-register.sh --down` stops it). With the
rig up, `phone/ctl.sh dial sip:2@asterisk` makes a real call into Asterisk's `Echo()` and
`docker compose -f phone/compose.test.yaml exec asterisk asterisk -rx "channel originate
PJSIP/phone application Echo"` rings the phone.

`--stock` exists because the repo's Asterisk image is a long source build; its `pjsip.conf` is a
copy of the `[phone]` sections from `asterisk/etc/pjsip.conf.tmpl` and must be kept in sync.

### Verified

- Image builds on arm64 (this Mac) and in CI on amd64; all modules the config loads exist in
  `baresip-core` 1.1.0 (`ctrl_tcp alsa g711 account menu uuid ausine aufile auloop`).
- `phone/test-register.sh --stock` passes: `Endpoint phone is now Reachable`, contact `Avail`,
  `reginfo` → `OK`.
- Outgoing and incoming calls as transcribed above, including `accept`, `sndcode` and `hangup`.
- Not verified: a real USB audio adapter (`alsa` module), the Pi, the repo Asterisk image
  (its build currently fails in menuselect, see the PR), and `group_add: audio` against a real
  `/dev/snd`.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `pjsip show endpoints` shows `phone` `Unavail`; baresip logs `401`/`403` | `PHONE_SIP_PASSWORD` differs between the two services. Fix `.env`, `docker compose up -d asterisk phone`. |
| baresip logs `Register: Connection timed out` | Asterisk not listening on `ASTERISK_HOST:5060`. On the Pi `ASTERISK_HOST` must be `127.0.0.1`. |
| `reginfo` shows `FB-ERR` | Same as above; registration failed and baresip is retrying (`regint=60`). |
| `alsa: could not open ... plughw:1,0` at the first call | `aplay -l` on the host and in the container; set `PHONE_AUDIO_DEVICE`. The container needs `/dev/snd` and the `audio` group (compose has both). |
| Call connects, one side silent | `docker compose exec phone alsamixer -c 1`: capture gain ~70 %, playback ~50 %. `rtp set debug on` in Asterisk. |
| `ausine: supports only 48kHz samplerate`, call drops with `Operation not supported` | `PHONE_AUDIO_SRATE=48000` when using `ausine`. |
| Backend cannot reach ctrl_tcp | `docker compose exec phone /usr/local/bin/healthcheck.sh`; from the Pi `nc -z 127.0.0.1 4444`; `PHONE_CTRL_BIND` must be `0.0.0.0` for the bridge-network backend. |
| Backend keeps getting disconnected | Something else connects to 4444 (a stray `ctl.sh`/`nc`, a port scanner). One client only. |
| Entrypoint exits with `is not a baresip module` | `PHONE_AUDIO_MODULE` typo; `docker run --rm --entrypoint ls tincan-phone ... /usr/lib/baresip/modules`. |
