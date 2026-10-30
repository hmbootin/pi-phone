# Backend API contract

Base URL `/api`. JSON everywhere. The UI and backend are built against this file; change it here
first. Auth: single shared parent password → session cookie (`POST /api/auth/login`). On the LAN
over Tailscale that is enough for v1.

## Contacts

`Contact`:
```json
{
  "id": 1,
  "name": "Grandma",
  "spoken_name": "Grandma Jo",
  "number": "+15555550123",
  "speed_dial": 2,
  "memory_key": "m1",
  "enabled": true,
  "inbound_allowed": true,
  "dnd_until": null,
  "max_call_minutes": null,
  "created_at": "2026-10-29T03:00:00Z"
}
```
`speed_dial` (0-9) and `memory_key` (`m1`..`m9`, `sos`; case-insensitive on input, lowercase on
output) are both optional and both unique across contacts. A contact with neither cannot be
dialed but can still call in. The phone's memory keys are dialed as extensions of the same name.
- `GET /api/contacts` → `Contact[]`
- `POST /api/contacts` body without `id`/`created_at` → `Contact` (409 `speed_dial_taken` /
  `memory_key_taken` if the digit or key is already used)
- `PATCH /api/contacts/{id}` partial → `Contact`
- `DELETE /api/contacts/{id}` → 204
- `POST /api/contacts/{id}/dnd` `{"minutes": 120}` or `{"until": "...Z"}` or `{"clear": true}` → `Contact`

## Features (what the other digits do)

`Feature`: `{"digit": 7, "kind": "fun_fact", "config": {"topic": "dinosaurs"}, "enabled": true}`
Kinds: `speed_dial` (implicit, from contacts), `weather`, `fun_fact`, `secret_message`, `mailbox`,
`song`, `none`.
- `GET /api/features` → `Feature[]` for all ten digits (digits with a contact report kind `speed_dial`)
- `PUT /api/features/{digit}` → `Feature`
- `POST /api/features/{digit}/preview` → `{"text": "...", "audio_url": "/api/audio/prompts/..."}` renders the prompt without a call

## Settings

```json
{
  "max_call_minutes": 10,
  "warning_seconds_before_end": 60,
  "quiet_hours": {"start": "19:30", "end": "07:30", "tz": "America/Chicago"},
  "daily_call_cap": 10,
  "ring_timeout_seconds": 25,
  "unknown_caller_policy": "reject" ,
  "notifications": {"ntfy_topic": null, "email": null},
  "trunk_caller_id": "+15555550100",
  "weather_location": {"lat": 30.27, "lon": -97.74, "name": "home"}
}
```
`unknown_caller_policy`: `reject` | `voicemail`.
- `GET /api/settings`, `PATCH /api/settings`

## Calls and recordings

`Call`: `{"id", "direction": "outbound"|"inbound"|"feature", "contact_id", "feature_kind", "started_at", "answered_at", "ended_at", "duration_seconds", "outcome", "recording_id"}`
`outcome`: `completed` | `no_answer` | `busy` | `rejected_dnd` | `rejected_quiet_hours` | `rejected_unknown` | `rejected_cap` | `time_cap` | `failed`.
- `GET /api/calls?limit=50&before=<id>` → `Call[]` newest first
- `GET /api/calls/active` → `Call | null`
- `POST /api/calls/active/hangup` → 204

`Recording`: `{"id", "kind": "call"|"secret"|"voicemail", "call_id", "contact_id", "created_at", "duration_seconds", "size_bytes", "backed_up_at", "listened": false, "audio_url"}`
- `GET /api/recordings?kind=&contact_id=&limit=` → `Recording[]`
- `GET /api/recordings/{id}/audio` → `audio/wav` (supports Range)
- `PATCH /api/recordings/{id}` `{"listened": true}` → `Recording`

## System

- `GET /api/system/status` → `{"asterisk": "connected"|"disconnected", "phone": "registered"|"unregistered", "trunk": "registered"|"unregistered"|"unconfigured", "version": "...", "disk_free_bytes", "backup": {"last_ok_at", "pending": 3}}`
- `GET /api/system/phone` → the phone-side state machine: `{"attached": true, "hardware": "none"|"fake"|"gpio", "state": "idle"|"dial_tone"|"dialing"|"ringing"|"in_call", "off_hook": bool, "dialed": "m1"|null, "sip": "connected"|"disconnected"}`. With no phone (`hardware: none`) `attached` is false and the other fields null.
- `GET /api/events` → Server-Sent Events: `call.started`, `call.ended`, `recording.created`, `status.changed`, `phone.changed` (same body as `/api/system/phone` minus `attached`/`hardware`)
- `POST /api/system/test-call` `{"contact_id": 1}` → rings the phone with a test prompt (parents verify the line works)

## Dev (only with `TINCAN_FAKE_ARI=1`)

- `POST /api/dev/simulate` drives the fakes. Phone hardware (needs `TINCAN_HARDWARE=fake`):
  `{"event": "offhook"}`, `{"event": "onhook"}`, `{"event": "key", "key": "m1"}` (keys: `0`-`9`, `*`, `#`,
  `m1`-`m9`, `sos`, `store`, `speaker`, `redial`, `flash`). Asterisk side: `{"event": "inbound", "from": "+1..."}`,
  `{"event": "answer"}` (far end picks up), `{"event": "hangup"}` (far end hangs up),
  `{"event": "offhook_dial", "digit": "2"}` (a channel enters Stasis directly, bypassing the phone).

## Errors

`{"error": {"code": "speed_dial_taken", "message": "..."}}` with an appropriate 4xx.
