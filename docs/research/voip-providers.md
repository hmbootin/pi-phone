# SIP trunk providers for Tin Can (US, low volume)

What we need: one US local number, inbound + outbound voice, SIP **registration** so the Pi behind
a home router needs no port forwarding, G.711 µ-law, caller ID set to our number, E911, and
optionally SMS on the same number for the "text DND 2h" feature. Volume: a handful of 5-minute
calls a day, so per-minute rates barely matter; monthly fees and setup friction do.

Prices checked 2026-10-29 from the linked pages. All are pay-as-you-go, no contract.

## Comparison

| | **VoIP.ms** | **Telnyx** | **Twilio Elastic SIP Trunking** | **Flowroute** |
|---|---|---|---|---|
| Local number / month | **$1.10** (homepage advertises "from $0.85") | **$1.00** (+$0.10/mo if SMS-enabled) | $1.15 | $1.00 (older pages say $0.50; confirm at signup) |
| Inbound / min | $0.009 (or $4.25/mo unlimited plan) | $0.0032 | $0.0034 | $0.005 |
| Outbound US / min | $0.01 ("premium" route; use it, "value" route has bad caller ID) | $0.005 | $0.0100 | $0.00833 |
| E911 / month | $1.50 + $1.50 one-time | $1.50 | $0.75 ($75 per 911 call without a registered address) | $1.39-1.50 + $95 per unregistered 911 call |
| SMS | Yes; $0.0075 out, enable per DID in portal, webhook or API | Yes; $0.004/part + carrier fees, inbound free, 10DLC registration required for A2P | Yes via Programmable Messaging on the same number; $0.0083/segment + carrier fees, 10DLC registration | Yes; $0.004/msg |
| **SIP registration (inbound without port forward)** | **Yes.** Sub-account with "NAT: Yes", DID routed to the sub-account; INVITEs ride the registration. | **Yes.** "Credentials" connection type; registration to `sip.telnyx.com`. IP-auth also available. | **No.** Origination goes to a public "Origination URI" you must host; docs say "configure your infrastructure not to register". Termination uses credential list or IP ACL. | Yes (up to 24 registrations); inbound can route to registered devices, or to a static URI. |
| Asterisk docs | [wiki](https://wiki.voip.ms/article/Asterisk_PJSIP), community | [official pjsip_wizard guide](https://developers.telnyx.com/docs/voice/sip-trunking/asterisk) | [official, IP-based](https://www.twilio.com/docs/sip-trunking/sample-configuration) | community only |
| Signup friction | Instant; small minimum deposit; KYC for E911 | Instant; identity verification before buying numbers, usually same day | Instant; must upgrade from trial | Email approval, 1-2 days (not verified this week) |
| Monthly cost for us (number + E911 + ~100 min) | **≈ $3.60** | **≈ $3.30** | ≈ $2.60 + the port-forward headache | ≈ $3.90 |

Sources: [VoIP.ms How it works](https://wiki.voip.ms/article/How_it_works),
[VoIP.ms extra services](https://wiki.voip.ms/article/Extra_Services_Costs),
[VoIP.ms SMS pricing note](https://main.voip.ms/?p=12822),
[Telnyx pricing](https://developers.telnyx.com/internal/pages/pricing),
[Telnyx numbers](https://telnyx.com/pricing/numbers), [Telnyx E911](https://support.telnyx.com/en/articles/1130683-e911-setup),
[Twilio SIP trunking pricing US](https://www.twilio.com/en-us/sip-trunking/pricing/us),
[Twilio SIP trunking docs](https://www.twilio.com/docs/sip-trunking), [Twilio SMS pricing](https://static1.twilio.com/en-us/sms/pricing/us),
[Flowroute pricing details](https://flowroute.com/pricing-details/),
[Flowroute registration limit](https://support.bcmone.com/docs/how-many-simultaneous-sip-registrations-are-allowed).

## Why not the consumer apps

- **Google Voice**: no SIP or API. The XMPP access OBi boxes used ended in 2014; the GVSIP
  workaround was shut down at Google's request in 2018. Only Google's own apps and Workspace
  SIP-link (enterprise, per-seat) remain. ([history](https://nerdvittles.com/creating-an-obi200-google-voice-trunk-to-use-with-asterisk/))
- **WhatsApp / FaceTime / Signal**: calling is end-to-end between their own clients; there is no
  third-party calling API (WhatsApp's Business API is messaging only; FaceTime has no API at all).
  You can't ring Grandma's WhatsApp from Asterisk.
- **Twilio Programmable Voice (TwiML)** would work but puts media and call logic in Twilio's
  cloud; we'd lose "everything is bridged on the Pi". Elastic SIP Trunking is the right Twilio product.
- **Direct SIP/WebRTC to contacts** (Linphone on Grandma's phone): free, but ADR 0004 explains why
  it fails with exactly the relatives this is for. Still supported per contact via a `sip:` URI.

## Recommendation

**Telnyx** as the default, **VoIP.ms** as the equally good alternative. Both register from
behind NAT, both do SMS on the number, both cost ~$3.50/month. Telnyx has first-party Asterisk
docs and slightly cleaner SMS webhooks; VoIP.ms has a 15-year hobbyist track record and the
friendliest portal for a one-number account. Avoid Twilio Elastic SIP Trunking **for this
design**: inbound requires a public SIP URI, which means a port forward on the home router (or a
static IP / a cloud SBC), contradicting the "no inbound ports" assumption in docs/architecture.md.
If the owner already has Twilio credit, the fix is a UDP 5060 + 10000-10100 port forward and
`external_media_address` in the transport; it works, it's just more exposed.

The ADR 0004 text says "VoIP.ms or Twilio"; this research suggests "VoIP.ms or Telnyx", with Twilio
as the port-forwarded option. The backend's templates should cover all three shapes below.

## pjsip.conf shapes

Common to all: Asterisk 20, `chan_pjsip`, one UDP transport, the trunk endpoint named `trunk`,
inbound context `from-trunk`, codecs `ulaw` only, and env vars `TRUNK_PROVIDER`, `TRUNK_USERNAME`,
`TRUNK_PASSWORD`, `TRUNK_HOST`, `TRUNK_DID` (E.164, e.g. `+15125550100`). The `identify` section is
what maps an inbound INVITE to the `trunk` endpoint; it is the thing that differs most.

```
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060
; behind a home router; Asterisk learns the public IP from the registration's Via/rport,
; but media needs it explicitly:
external_media_address=${PUBLIC_IP}      ; optional for registration-based providers; required for Twilio
external_signaling_address=${PUBLIC_IP}  ; same
local_net=192.168.0.0/16
local_net=10.0.0.0/8
```

### VoIP.ms (registration)

Portal: Sub Accounts → create `${ACCOUNT}_tincan` with Protocol SIP, Authentication User/Password,
Device type "Asterisk, IP PBX, Gateway or VoIP Switch", **NAT: Yes**, CallerID Number = your DID,
Allowed codecs: G.711U. DID Numbers → Manage DIDs → route the DID to that sub-account and note its
**Point of Presence** (e.g. `dallas1.voip.ms`, `seattle1.voip.ms`); register to that host, not the
generic one. Sub-account username has the form `123456_tincan`.

```
[trunk]
type=endpoint
transport=transport-udp
context=from-trunk
disallow=all
allow=ulaw
outbound_auth=trunk-auth
aors=trunk
from_user=${TRUNK_USERNAME}           ; 123456_tincan
from_domain=${TRUNK_HOST}             ; dallas1.voip.ms
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
dtmf_mode=rfc4733
send_pai=yes
callerid=Tin Can <${TRUNK_DID_DIGITS}>    ; 10 digits, no +

[trunk-auth]
type=auth
auth_type=userpass
username=${TRUNK_USERNAME}
password=${TRUNK_PASSWORD}

[trunk]
type=aor
contact=sip:${TRUNK_HOST}:5060
qualify_frequency=60

[trunk-reg]
type=registration
transport=transport-udp
outbound_auth=trunk-auth
server_uri=sip:${TRUNK_HOST}:5060
client_uri=sip:${TRUNK_USERNAME}@${TRUNK_HOST}:5060
contact_user=${TRUNK_USERNAME}
retry_interval=60
forbidden_retry_interval=600
expiration=300
line=yes
endpoint=trunk

[trunk-identify]
type=identify
endpoint=trunk
match=${TRUNK_HOST}       ; hostname is resolved; VoIP.ms POPs have stable IPs
```

Dial out as `PJSIP/1${NUMBER10}@trunk` (VoIP.ms wants 11 digits, `1NXXNXXXXXX`; E.164 with `+`
is also accepted on recent accounts). Inbound INVITE's request user is the 10-digit DID.
VoIP.ms also offers TLS on 5061 + SRTP ("Encrypted SIP" on the sub-account); add
`media_encryption=sdes` and a `tls` transport if you want it. ([VoIP.ms wiki Asterisk PJSIP](https://wiki.voip.ms/article/Asterisk_PJSIP);
[worked example, 2026](https://nramkumar.org/tech/blog/2026/05/04/asterisk-with-voip-ms-sip-trunk-in-debian-12/))

### Telnyx (credentials connection, registration)

Portal: Voice → SIP Connections → add, type **Credentials**; copy the generated username/password
("Auth Detail"). Assign the number to the connection. Outbound Voice Profile attached to the
connection. Host is `sip.telnyx.com` (anycast; signaling IPs for the US region are currently
`192.76.120.10` and `64.16.250.10`, check [the IP list](https://sip.telnyx.com/)).

```
[trunk]
type=endpoint
transport=transport-udp
context=from-trunk
disallow=all
allow=ulaw
outbound_auth=trunk-auth
aors=trunk
from_user=${TRUNK_USERNAME}
from_domain=sip.telnyx.com
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
dtmf_mode=rfc4733
callerid=Tin Can <${TRUNK_DID}>        ; E.164 with +

[trunk-auth]
type=auth
auth_type=userpass
username=${TRUNK_USERNAME}
password=${TRUNK_PASSWORD}

[trunk]
type=aor
contact=sip:sip.telnyx.com:5060
qualify_frequency=60

[trunk-reg]
type=registration
transport=transport-udp
outbound_auth=trunk-auth
server_uri=sip:sip.telnyx.com:5060
client_uri=sip:${TRUNK_USERNAME}@sip.telnyx.com
contact_user=${TRUNK_USERNAME}
retry_interval=60
expiration=600
line=yes
endpoint=trunk

[trunk-identify]
type=identify
endpoint=trunk
match=192.76.120.10
match=64.16.250.10
match=sip.telnyx.com
```

Dial out as `PJSIP/${E164}@trunk` (`+1…`). Inbound request user is the E.164 number with `+`.
Telnyx's own guide uses `pjsip_wizard.conf` with `sends_registrations=yes`, `remote_hosts=sip.telnyx.com:5060`,
`registration/expiration=600`; the above is the equivalent in plain `pjsip.conf`.
([Telnyx Asterisk guide](https://developers.telnyx.com/docs/voice/sip-trunking/asterisk))

### Twilio Elastic SIP Trunking (no registration; needs a public port)

Console: Elastic SIP Trunking → Trunks → create. **Termination**: SIP URI `tincan.pstn.twilio.com`,
add a Credential List (`${TRUNK_USERNAME}`/`${TRUNK_PASSWORD}`). **Origination**: Origination URI
`sip:${PUBLIC_IP_OR_DDNS}:5060`. Assign the number. Router: forward UDP 5060 and 10000-10100 to the
Pi. Twilio's signaling comes from published /30 ranges per region and media from `168.86.128.0/18`
UDP 10000-60000 ([current list](https://www.twilio.com/docs/sip-trunking/ip-addresses), verified 2026-10-29; allow all regions, failover may use any).

```
[trunk]
type=endpoint
transport=transport-udp
context=from-trunk
disallow=all
allow=ulaw
outbound_auth=trunk-auth
aors=trunk
from_user=${TRUNK_USERNAME}
from_domain=tincan.pstn.twilio.com
direct_media=no
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
dtmf_mode=rfc4733
callerid=Tin Can <${TRUNK_DID}>        ; must be a number on the Twilio account

[trunk-auth]
type=auth
auth_type=userpass
username=${TRUNK_USERNAME}
password=${TRUNK_PASSWORD}

[trunk]
type=aor
contact=sip:tincan.pstn.twilio.com
qualify_frequency=60

; no [registration] section

[trunk-identify]
type=identify
endpoint=trunk
match=54.172.60.0/30
match=54.244.51.0/30
match=54.171.127.192/30
match=35.156.191.128/30
match=54.65.63.192/30
match=54.169.127.128/30
match=54.252.254.64/30
match=177.71.206.192/30
```

Dial out as `PJSIP/${E164}@trunk`; numbers must be E.164 with `+` or Twilio returns 400. SMS is a
separate Programmable Messaging webhook on the same number.
([Twilio docs](https://www.twilio.com/docs/sip-trunking), [pricing](https://www.twilio.com/en-us/sip-trunking/pricing/us))

### Flowroute (registration)

Same shape as VoIP.ms with `server_uri=sip:sip.flowroute.com`, `client_uri=sip:${TECH_PREFIX}@sip.flowroute.com`,
username = your 8-digit tech prefix, password = the SIP password from Interconnection → SIP
Credentials; set the DID's route to "SIP registration". Identify on `sip.flowroute.com` plus their
published POP IPs. Community guides only; nothing official for pjsip.

## What the backend should check for

- `pjsip show registrations` shows `trunk-reg … Registered` (VoIP.ms, Telnyx, Flowroute) and the
  UI maps that to `trunk: registered`. For Twilio there is no registration; use
  `pjsip show endpoints` → `trunk` contact `Avail` (OPTIONS qualify against the termination URI)
  and surface it as `registered` too.
- Inbound DID format differs: VoIP.ms 10 digits, Telnyx/Twilio E.164. Normalise in `from-trunk`
  before `Stasis()`, or in the backend's `StasisStart` handler.
- Caller ID on inbound arrives in `From`; Telnyx and Twilio also send `P-Asserted-Identity`.
  Match contacts on the last 10 digits.
