# 0006 What touches the cloud, and why

Status: accepted. 2026-10-29.

Self-hosted by default. These things leave the house, each for a reason:

| What | Why it can't be local | Choice |
|------|----------------------|--------|
| SIP trunk | Only a carrier can hand out a phone number | ADR 0004 |
| Recording backup | SD cards die; a house fire shouldn't take the memories | `rclone` to Backblaze B2 or S3, encrypted at rest with `rclone crypt`. Copy, never move. |
| Push notifications | Parents' phones are elsewhere | `ntfy.sh` (or self-hosted ntfy later), fallback email via SMTP |
| Inbound SMS for DND ("text STOP 2h") | The provider must reach our webhook | Tailscale Funnel exposes one path of the backend; off by default. The parent app can set DND without it. |
| Updates | Images are built in CI | GitHub Container Registry; the Pi pulls, nothing pushes in |
| Weather | Needs a forecast | Open-Meteo, no key, no account |

Not in the cloud: contacts, call logs, the UI, TTS (Piper runs on the Pi), fun facts (a local JSON
list the parent app edits; an LLM-generated feed is an optional later feature).
