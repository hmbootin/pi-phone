# Runbook

Operations on the Pi. Everything below assumes `ssh tincan` works (see [remote-dev.md](remote-dev.md))
and uses these aliases on the Pi:

```
alias tc='docker compose -f /opt/tincan/compose.yaml'
alias ast='tc exec asterisk asterisk -rx'
```

## First boot

[deploy/README.md](../deploy/README.md) §1. Check it worked:

```
systemctl status tincan tincan-update.timer tincan-backup.timer
tc ps                       # asterisk healthy, backend healthy
ast "pjsip show endpoints"  # phone: Avail once the phone service registers; trunk: Avail if configured
curl -s localhost:8080/api/system/status | jq
```

## Set or change the trunk

1. Edit `/opt/tincan/.env`: `TRUNK_PROVIDER=voipms|twilio`, `TRUNK_HOST`, `TRUNK_USERNAME`,
   `TRUNK_PASSWORD`, `TRUNK_DID` (E.164). Provider specifics are in
   `docs/research/voip-providers.md` and the comments in `asterisk/etc/pjsip_trunk_*.conf.tmpl`.
2. `tc up -d asterisk` (recreates the container; the entrypoint re-renders the templates).
3. `ast "pjsip show registrations"` should show `Registered` within ~30 s. `ast "pjsip show endpoint trunk"` for details.
4. Set `trunk_caller_id` in the parent UI settings to the same number.
5. Test: parent UI → System → Test call, then have someone call the number.

Twilio needs the Pi's public IP in the trunk's IP ACL **or** credential-list auth; the template
uses credentials. VoIP.ms: enable the sub-account, set it to "SIP", NAT = yes.

## Rotate passwords

| Secret | Where | After changing |
|--------|-------|----------------|
| `TINCAN_PARENT_PASSWORD` | `.env` | `tc up -d backend` |
| `TINCAN_SECRET_KEY` | `.env` | `tc up -d backend`; everyone is logged out |
| `ARI_PASSWORD` | `.env` | `tc up -d` (both containers read it) |
| `PHONE_SIP_PASSWORD` | `.env` (asterisk and phone services) | `tc up -d asterisk phone`; phone re-registers in <1 min |
| `TRUNK_PASSWORD` | provider portal first, then `.env` | `tc up -d asterisk` |
| rclone crypt passwords | don't. Changing them makes every existing backup unreadable. Rotate the B2 application key instead. |

Generate with `openssl rand -hex 24`.

## Check registration status

```
ast "pjsip show endpoints"        # the overview
ast "pjsip show contacts"         # where the phone service registered from and its RTT
ast "pjsip show registrations"    # our registration to the trunk
ast "pjsip set logger on"         # SIP trace to the console; `tc logs -f asterisk`
ast "rtp set debug on"            # when audio is one-way
```

`phone` not `Avail`: the phone service is down or has the wrong password. `tc logs phone`. `trunk` `Unavailable`: wrong host/credentials, or the
provider blocks the Pi's IP; `pjsip set logger on` shows the 401/403.

## Backups

`sudo /opt/tincan/backup.sh` runs one now; `journalctl -u tincan-backup -n 100` shows the last
nightly. What is off-site: `tc run --rm backup lsd tincan-backup:` then
`tc run --rm backup ls tincan-backup:recordings | tail`. `/data/backup/last_ok` holds the last
success time (the UI's system status reads it if the backend supports it).

## Restore from backup

Needs `/opt/tincan/rclone.conf` with the **same** crypt passwords. The compose `backup` service
mounts `/data` read-only on purpose (it can only ever copy out), so a restore uses rclone directly:

```
sudo systemctl stop tincan
rc() { docker run --rm -v /data:/data -v /opt/tincan/rclone.conf:/config/rclone/rclone.conf:ro rclone/rclone:1.68 "$@"; }
# recordings and prompts: copy back, never --delete anything local
rc copy tincan-backup:recordings /data/recordings
rc copy tincan-backup:asterisk/recording /data/asterisk/recording
rc copy tincan-backup:prompts /data/prompts
# database: latest snapshot, or a dated one (rc ls tincan-backup:db)
rc copy tincan-backup:db/tincan.db /data/backup/
sudo cp /data/tincan.db /data/tincan.db.broken-$(date +%F) 2>/dev/null || true
sudo sqlite3 /data/backup/tincan.db "PRAGMA integrity_check;"   # must print ok
sudo cp /data/backup/tincan.db /data/tincan.db
sudo chown -R 2000:tincan /data && sudo systemctl start tincan
```

## Roll back a release

```
sudo /opt/tincan/update.sh --rollback          # one step back, pins the channel
sudo /opt/tincan/update.sh --version v1.2.0    # any specific release
echo stable | sudo tee /opt/tincan/channel     # when fixed upstream, resume auto-updates
```

`update.sh` already does this automatically when a new version's backend fails its healthcheck
for 2 minutes; `journalctl -u tincan-update` tells you.

## Disk full

Symptoms: calls connect but no recording, backend 500s, `df -h /data` at 100%.

1. `du -sh /data/* /var/lib/docker` to see which.
2. Docker: `docker system prune -f` (old images from updates; `update.sh` prunes but a failed
   run may not have). Logs are capped at 50 MB per container by `compose.yaml`.
3. Recordings: **confirm they are backed up first** (`tc run --rm backup check /data/recordings tincan-backup:recordings --one-way`),
   then move (not delete) the oldest year to the SSD or a USB stick. The rule is recordings are
   immutable; the backup is the copy that counts, the Pi is the cache.
4. Long term: USB SSD (deploy/README.md).

## The Pi died

Rebuild is bootstrap + restore; nothing on the host is hand-configured.

1. New SD/SSD, Raspberry Pi OS Lite 64-bit, same hostname `tincan`.
2. `deploy/README.md` §1 steps 2–4 with the **old `.env`** (you kept a copy, or re-create: new
   `ARI_PASSWORD`/`TINCAN_SECRET_KEY` are fine, but `PHONE_SIP_PASSWORD` must match the phone service and
   `TRUNK_*` the provider).
3. Put `rclone.conf` back, then **Restore from backup** above.
4. In Tailscale's admin console delete the old `tincan` machine so MagicDNS points at the new one.
5. `ast "pjsip show endpoints"`: phone and trunk `Avail`. Make a test call.

If the SD card is readable, `/data` and `/opt/tincan/.env` from it beat any backup.

## Quick triage

| Symptom | Look at |
|---------|---------|
| Nothing in the earpiece | USB audio adapter: `aplay -l` on the host, then `tc logs phone`; registration: `ast "pjsip show endpoints"` |
| Keys do nothing | `tc logs backend` for the key scanner; check the GPIO bundle and that the hook reads off-hook |
| No ring | `aplay` a WAV to the Pi headphone jack on the host; check the amp's 5 V |
| Dials, nothing happens | `tc logs backend`: is it connected to ARI? `curl -u $ARI_USER:$ARI_PASSWORD localhost:8088/ari/asterisk/info` |
| One-way audio | `ast "rtp set debug on"`; check `alsamixer` capture gain on the USB adapter; trunk needs `external_media_address` if the Pi is behind a double NAT |
| Rings but nobody answers / family can't call in | trunk registration; inbound DID routing on the provider side points at the SIP registration |
| No recording in UI | `ls -la /data/asterisk/recording /data/recordings`, ownership 2000:tincan |
| UI unreachable | `tc ps`; `curl localhost:8080/healthz`; Tailscale: `tailscale status` |
| Update stuck | `journalctl -u tincan-update -n 50`; `cat /opt/tincan/channel /opt/tincan/.previous-version` |
