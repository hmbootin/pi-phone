# 0003 Asterisk as the media engine, application logic in Python via ARI

Status: accepted. 2026-10-29.

We need: SIP registration for the phone service and the trunk, RTP handling, bridging, recording both legs,
playing prompts, DTMF events, and reliable hangup. Asterisk 20 LTS does all of it, runs fine on a Pi
4, and has twenty years of answers on the internet. FreeSWITCH is comparable but heavier and less
documented for hobbyists. Writing our own SIP/RTP stack would make recording and bridging our problem. (baresip is still
used, but only as the dumb SIP phone on the handset side; see ADR 0002.)

The dialplan is deliberately dumb. Both contexts (`from-phone`, `from-trunk`) hand off to
`Stasis(tincan, ...)` immediately. The backend owns every decision through ARI (REST +
WebSocket). This keeps contacts and policy in SQLite and out of Asterisk config, so the parent app
never has to reload Asterisk, and the backend can be unit-tested against a fake ARI.

Alternatives for the glue: AGI (synchronous, per-call script; awkward for timers and bridging) and
AMI (older, event-soup). ARI is the modern one.

Python ARI clients are mostly abandoned; the backend ships its own small async client over `httpx`
and `websockets`. It's ~200 lines and we control it.
