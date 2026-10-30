# Deploying Tin Can to the Pi

Everything on the Pi is Docker Compose plus three systemd units (ADR 0005). This directory is
copied to `/opt/tincan` by `bootstrap.sh`; nothing else lives on the host.

| File | Purpose |
|------|---------|
| `bootstrap.sh` | One-time Pi setup: Docker, Tailscale, `/data`, `/opt/tincan`, systemd units. Idempotent. |
| `compose.yaml` | The three services: `asterisk`, `backend`, `backup` (profile, run by the timer). |
| `compose.dev.yaml` | Override that builds images on the Pi from a synced checkout (`mise run deploy-dev`). |
| `.env.example` | Every setting, documented. Becomes `/opt/tincan/.env`. |
| `rclone.conf.example` | Backblaze B2 + `crypt` remote for off-site backups. Becomes `/opt/tincan/rclone.conf`. |
| `update.sh` | OTA: follow the `stable` channel or pin `--version vX.Y.Z`; `--rollback`. Auto-rolls back if the backend doesn't come up healthy. |
| `backup.sh` | Nightly: SQLite snapshot + `rclone copy` recordings/prompts/db. Copy, never sync. |
| `systemd/` | `tincan.service` (compose up at boot), `tincan-update.timer` (10 min), `tincan-backup.timer` (03:15). |

## 1. First boot

1. Flash **Raspberry Pi OS Lite 64-bit** with the Imager. In the OS customisation screen set the
   hostname to `tincan`, your user, your SSH key, Wi-Fi if you must (Ethernet is strongly
   preferred for RTP). Boot it.
2. SSH in and run bootstrap:

   ```
   sudo apt-get install -y git
   git clone https://github.com/<owner>/pi-phone && cd pi-phone
   sudo GHCR_OWNER=<owner> ./deploy/bootstrap.sh
   ```

   It prints a Tailscale login URL partway through; open it on your phone or laptop. When it
   finishes it tells you what to edit.
3. Fill in `/opt/tincan/.env`: `TINCAN_PARENT_PASSWORD`, and `TRUNK_*` once you have a trunk
   (`TRUNK_PROVIDER=none` is fine for dial tone and features, M1 on the roadmap). The ARI, SIP
   and secret keys were generated for you.
4. Start it: `sudo systemctl start tincan`, then `docker compose -f /opt/tincan/compose.yaml logs -f`.
   The first pull is a few hundred MB.
5. Point the ATA at the Pi: SIP server = the Pi's LAN IP, user `phone`, password =
   `PHONE_SIP_PASSWORD`. See `hardware/` for the ATA settings. `pjsip show endpoints` inside the
   Asterisk container should show `phone` as `Avail`.
6. Open `http://tincan:8080` (Tailscale) or `http://<pi-ip>:8080` (LAN) and log in with the
   parent password.

## 2. Backups

1. Create a B2 bucket and an application key with no `deleteFiles` capability.
2. `sudo cp /opt/tincan/rclone.conf.example /opt/tincan/rclone.conf && sudo chmod 600 $_`, fill in the
   account, key, bucket, and two `rclone obscure`d passwords. **Write the crypt passwords down
   somewhere outside the house**; without them the backup is noise.
3. Test: `sudo /opt/tincan/backup.sh`. Then `journalctl -u tincan-backup` after the first night.

## 3. Releases and updates

From your laptop: `mise run release -- v1.2.3`. That pushes a tag; `.github/workflows/release.yml`
builds the UI, multi-arch images, pushes them to GHCR as `v1.2.3` and `stable`, and publishes a
GitHub release. Within 10 minutes every Pi whose `/opt/tincan/channel` says `stable` pulls it,
restarts, and rolls back on its own if the backend's healthcheck fails.

By hand on the Pi:

```
sudo /opt/tincan/update.sh --check            # what would happen
sudo /opt/tincan/update.sh                    # do it now
sudo /opt/tincan/update.sh --version v1.2.2   # pin (also writes the channel file)
sudo /opt/tincan/update.sh --rollback         # previous version, and pins to it
echo stable | sudo tee /opt/tincan/channel    # back on the release train
journalctl -u tincan-update -n 50             # what the timer has been doing
```

The GHCR packages must be **public** (or the Pi needs `docker login ghcr.io`): GitHub → the
package → Package settings → Change visibility. Do this once after the first release.

## 4. Developing against the Pi

See [docs/remote-dev.md](../docs/remote-dev.md). Short version: `mise run deploy-dev` syncs your
checkout and builds on the Pi; `mise run logs`; `mise run pi -- <cmd>`.

## 5. Operations

[docs/runbook.md](../docs/runbook.md): rotate passwords, change trunk, restore, rollback, disk
full, dead Pi.

## USB SSD

SD cards wear out; recordings are the point of this project. A USB 3 SSD (any 128 GB+ SATA or
NVMe in a UASP enclosure) mounted at `/data` is the single best reliability upgrade:

```
sudo mkfs.ext4 -L tincan-data /dev/sda1
echo 'LABEL=tincan-data /data ext4 defaults,noatime,nofail,x-systemd.device-timeout=10 0 2' | sudo tee -a /etc/fstab
sudo systemctl stop tincan && sudo mv /data /data.sd && sudo mkdir /data && sudo mount /data
sudo rsync -a /data.sd/ /data/ && sudo ./deploy/bootstrap.sh && sudo systemctl start tincan
```

`nofail` means the Pi still boots (without Tin Can) if the drive is unplugged.
