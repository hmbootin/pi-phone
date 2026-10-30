# Asterisk configuration

Static Asterisk 20 config for the `asterisk` container. Nothing here changes at runtime; contacts
and policy live in the backend's SQLite. The only dynamic parts are credentials, which the
container entrypoint renders from environment variables at start.

## Contract for the entrypoint (`asterisk/entrypoint.sh`, owned by deploy)

1. Copy `asterisk/etc/*` to `/etc/asterisk/`.
2. For every `*.conf.tmpl`, run `envsubst` and write the result without the `.tmpl` suffix
   (`ari.conf.tmpl` -> `ari.conf`, `pjsip.conf.tmpl` -> `pjsip.conf`, ...). Restrict envsubst to
   the variable names below so `${EXTEN}`-style dialplan variables are never touched (only
   `extensions.conf` has them and it is not a template, but be safe:
   `envsubst '$ARI_USER $ARI_PASSWORD ...'`).
3. Pick the trunk by `TRUNK_PROVIDER` and produce `/etc/asterisk/pjsip_trunk.conf`:
   - `voipms` -> render `pjsip_trunk_voipms.conf.tmpl`
   - `telnyx` -> render `pjsip_trunk_telnyx.conf.tmpl`
   - `twilio` -> render `pjsip_trunk_twilio.conf.tmpl`
   - `none` (default) -> copy `pjsip_trunk_none.conf`
   `pjsip.conf` does `#include pjsip_trunk.conf`, so the file must exist.
4. `mkdir -p /data/asterisk/recording` and make sure the Asterisk user can write it and read
   `/data/prompts` (same uid/gid as the backend, or group-writable `/data`).
5. `exec asterisk -f -U asterisk` (foreground, no console).

Delete the rendered `*.conf` only; never write secrets back into `asterisk/etc`.

## Environment variables

| Var | Used by | Required |
|-----|---------|----------|
| `ARI_USER` | `ari.conf.tmpl` | yes (backend uses the same name) |
| `ARI_PASSWORD` | `ari.conf.tmpl` | yes |
| `PHONE_SIP_PASSWORD` | `pjsip.conf.tmpl` | yes; configure the same password on the ATA, user `phone` |
| `EXTERNAL_IP` | `pjsip.conf.tmpl` | optional; empty is fine on a LAN / registration-based trunk |
| `LOCAL_NET` | `pjsip.conf.tmpl` | optional, e.g. `192.168.1.0/24`; empty is fine |
| `TRUNK_PROVIDER` | entrypoint | `voipms`, `telnyx`, `twilio`, or `none` (default) |
| `TRUNK_USERNAME` | trunk templates | with voipms/twilio |
| `TRUNK_PASSWORD` | trunk templates | with voipms/twilio |
| `TRUNK_HOST` | trunk templates | voipms POP (`chicago1.voip.ms`) or Twilio termination host (`x.pstn.twilio.com`) |
| `TRUNK_DID` | trunk templates | our number, digits only (`15555550100`) |

`envsubst` has no conditionals, so empty optional variables must be allowed to render as empty
values (`external_media_address =` with nothing after it is valid for PJSIP).

## What each file does

| File | Purpose |
|------|---------|
| `asterisk.conf` | Paths. `astspooldir => /data/asterisk`, so ARI recordings land in `/data/asterisk/recording/` on the shared volume |
| `modules.conf` | `autoload=no`; loads chan_pjsip, RTP, ulaw/alaw/gsm, wav, HTTP+WebSocket, ARI, Stasis, MixMonitor. `chan_sip` and everything else is `noload` |
| `http.conf` | HTTP on `0.0.0.0:8088` for ARI (Compose-internal only) |
| `ari.conf.tmpl` | One ARI user |
| `rtp.conf` | RTP ports 10000-10100 |
| `pjsip.conf.tmpl` | UDP transport on 5060, the `phone` endpoint (ATA), `#include pjsip_trunk.conf` |
| `pjsip_trunk_voipms.conf.tmpl` | `trunk` endpoint + outbound registration to VoIP.ms (inbound rides the registration; no port forward) |
| `pjsip_trunk_telnyx.conf.tmpl` | Same shape for Telnyx credentials connections (registration to `sip.telnyx.com`) |
| `pjsip_trunk_twilio.conf.tmpl` | `trunk` endpoint for Twilio Elastic SIP Trunking (no REGISTER; needs 5060/udp + RTP reachable) |
| `pjsip_trunk_none.conf` | No trunk. Backend reports trunk `unconfigured` |
| `extensions.conf` | `from-phone`: `_X`/`_X.` -> `Stasis(tincan,dial,${EXTEN})`; `from-trunk`: `_X.` -> `Stasis(tincan,inbound)`; both fall through to a safe beep-and-hangup if the backend is down |
| `logger.conf` | Console + messages log |

## Ports

- `5060/udp` SIP (LAN for the ATA; internet only for Twilio)
- `10000-10100/udp` RTP (same)
- `8088/tcp` ARI, internal only; never publish it

## How the backend names things

- ATA endpoint `PJSIP/phone`, trunk endpoint `PJSIP/trunk`; outbound calls are originated as
  `PJSIP/<E.164>@trunk` (or `PJSIP/sip:user@host` for direct SIP contacts).
- Stasis app `tincan` (`ARI_APP` in the backend). Args: `dial,<digits>`, `inbound`; the backend's
  own originates use `far`, `ring`, `test`.
- Recording names are `<yyyy>/<mm>/call-<id>` etc.; Asterisk writes
  `/data/asterisk/recording/<yyyy>/<mm>/call-<id>.wav`. The backend pre-creates the directories.
- Prompts are played as `sound:/data/prompts/<sha>` (8 kHz s16 mono WAV).

## ATA settings (Grandstream HT801)

- SIP server: the Pi's LAN IP, port 5060; user/auth ID `phone`; password `PHONE_SIP_PASSWORD`.
- Dial plan: `{x}` so each digit is sent immediately. Disable "dial tone timeout" or set it short.
- Codec: PCMU (ulaw) first. DTMF: RFC2833. Disable "use random port".
- Check with `asterisk -rx "pjsip show endpoints"`: `phone` must show `Avail`.
