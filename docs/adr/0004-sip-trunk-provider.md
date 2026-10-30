# 0004 Reach family on their real phones through a SIP trunk provider

Status: accepted. 2026-10-29.

Family should be able to call the toddler's number from their normal phones, and the toddler should
reach them wherever they are. That means a real phone number on the PSTN, which only a carrier can
provide. Options:

- **Google Voice**: no supported SIP/API access; the old XMPP trick is dead. Out.
- **WhatsApp / FaceTime / Signal**: no third-party calling API. Out.
- **Twilio Programmable Voice (REST/TwiML)**: media goes through Twilio; we'd need a Twilio SIP
  domain or Twilio's media streams. Workable but more moving parts than a trunk.
- **Twilio Elastic SIP Trunking**: a plain SIP trunk with excellent docs. But it does not support
  SIP registration for inbound: Twilio must be given a public origination URI, which means a port
  forward or Tailscale Funnel to the Pi. Supported as a provider template, not the default.
- **Telnyx**: SIP trunk with credential-based registration (inbound works behind NAT), cheap DIDs,
  SMS on the same number, good docs. Preferred.
- **VoIP.ms**: cheapest, registration-based, SMS available, scrappier docs. Fine alternative.
- **Direct SIP/WebRTC to contacts' phones (Linphone app, Asterisk as the server)**: free, fully
  self-hosted, but every contact must install an app and keep it alive, which fails exactly with the
  grandparents this is for. Kept as an optional per-contact transport (`sip:` URI in the number field).

Decision: the backend treats the trunk as one PJSIP endpoint named `trunk`. Credentials come from env
vars at container start; `asterisk/etc/` has a `pjsip_trunk_<provider>.conf.tmpl` per provider.
Default to Telnyx (or VoIP.ms). Only pick Twilio if you are willing to expose SIP to the internet.
See `docs/research/voip-providers.md` for the comparison, current prices, and the exact pjsip shapes.

Caller-ID is the whitelist. Inbound calls from numbers that aren't contacts never ring the phone.
