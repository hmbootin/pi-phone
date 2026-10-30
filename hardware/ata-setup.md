# Configuring the Grandstream HT801 V2 for Asterisk on the Pi

Setting names below are verbatim from the HT80x V2 Administration Guide
(https://documentation.grandstream.com/wp-content/uploads/2026/10/HT80x-V2-–-Administration-Guide.pdf,
Oct 2026). The V1 HT801 has the same settings under slightly different page names (Profile 1 /
FXS Port 1 instead of FXS Port → tabs). Time: 20 minutes.

## 0. Before you start

- The Pi is on the LAN with Compose up (`deploy/README.md`) and you know its IP or
  `tincan.local`. The Asterisk container exposes UDP/TCP 5060 and UDP 10000-10100 on the host.
- `PHONE_SIP_PASSWORD` is set in the Pi's `.env`. Generate one: `openssl rand -base64 24 | tr -d '/+='`.
- Plug the HT801 into Ethernet and power. Wait ~60 s. The POWER, LINK and PHONE LEDs settle.
- Plug the phone into the green **PHONE** RJ11 port (not the Ethernet port).

## 1. Find its IP and log in

1. Lift the handset, dial `***` (you hear "Enter a menu option"), then `02`. The IVR reads the
   IP address. (`01` tells you DHCP/static, `10` the MAC, `16` firmware version, `99` + `9` reboots.)
   Or look at your router's DHCP leases for `Grandstream`.
2. Browse to `http://<ata-ip>`. Username `admin`; the password is the **random one printed on the
   sticker on the back of the unit** (V2). V1 units use `admin`/`admin`.
3. It will ask you to change the admin password. Do it; write it in your password manager.
4. Maintenance → Upgrade: set "Upgrade Via" HTTPS, "Firmware Server Path" `fm.grandstream.com/gs`
   and reboot once to pull the latest firmware. Optional but the V2 first-run firmware had bugs.
5. Give it a DHCP reservation on your router so the IP never changes (Asterisk doesn't care,
   but you will when you need the web UI again).

## 2. FXS Port → General Settings

| Setting | Value |
|---------|-------|
| Profile Active | Yes |
| Primary SIP Server | `<pi-ip>` (e.g. `192.168.1.20`). Port 5060 is default; use `192.168.1.20:5060` if you changed it. |
| Failover SIP Server, Outbound Proxy | blank |
| SIP User ID | `phone` |
| Authenticate ID | `phone` |
| Authenticate Password | the value of `PHONE_SIP_PASSWORD` |
| Name | `Tin Can` (shows as caller name internally) |
| Allow DHCP Option 120 (override SIP server) | No |

## 3. FXS Port → SIP Settings

| Setting | Value | Why |
|---------|-------|-----|
| SIP Transport | UDP | |
| Register Expiration | 5 (minutes) | default 60; a shorter value makes `pjsip show contacts` reflect a yanked cable sooner |
| Unregister On Reboot | All | clean re-registration after a power blip |
| NAT Traversal | No | same LAN; STUN/keep-alive only add noise |
| Enable SIP OPTIONS/NOTIFY Keep Alive | Yes | ATA pings Asterisk every 30 s and re-registers if 3 are lost; Asterisk pings it back (`qualify_frequency`) |
| SIP OPTIONS/NOTIFY Keep Alive Interval | 30 | |
| SUBSCRIBE for MWI | No | we have no voicemail lamp |
| Check SIP User ID for Incoming INVITE | Yes | ignores stray INVITEs that aren't for `phone` |
| Authenticate Incoming INVITE | No | Asterisk is the only caller on this LAN |
| Allow Incoming SIP Messages from SIP Proxy Only | Yes | (if present on your firmware) |

## 4. FXS Port → Codec Settings

| Setting | Value |
|---------|-------|
| Vocoder Settings (in listed order): choice 1 | PCMU |
| choice 2 | PCMA |
| choices 3-8 | PCMU (i.e. nothing else) |
| Voice Frames per TX | 2 (= 20 ms packets) |
| Silence Suppression | No |
| Preferred DTMF: 1st | RFC2833 |
| 2nd / 3rd | In-audio / SIP INFO |
| DTMF Payload Type | 101 |
| Jitter Buffer Type | Adaptive |
| Fax Mode | Pass-Through (T.38 negotiation is pointless here) |

## 5. FXS Port → Analog Signal Line Configuration

| Setting | Value | Note |
|---------|-------|------|
| Enable Pulse Dialing | No (Yes for a rotary phone) | |
| Enable Hook Flash | **No** | a dropped cradle must not become a "flash" |
| On Hook Timing | 400 (ms, default) | raise to 600-800 if the toddler's fumbling causes accidental hangups |
| Loop Current Disconnect | No | |
| Ring Frequency | 20Hz | |
| Ring Power | 45Vrms (55Vrms for a mechanical bell) | |
| Rx gain / Tx gain | 0 dB | adjust here, not in Asterisk, if either side is quiet |
| Disable Line Echo Canceller (LEC) | No | |

## 6. FXS Port → Call Settings

| Setting | Value | Note |
|---------|-------|------|
| **Dial Plan** | `{x}` | exactly one digit, sent immediately. The default `{ x+ \| +x+ \| *x+ \| *xx*x+ }` would wait 4 s after the key. |
| No Key Entry Timeout | 4 | irrelevant with `{x}` but leave it |
| Early Dial | No | |
| Dial Plan Prefix | blank | |
| Use # as Dial Key | No | `#` isn't in our plan anyway |
| Enable # as Redial Key | No | |
| **Off-hook Auto Dial** | blank (hotline mode: an extension such as `0`) | if set, the ATA never collects digits; the backend treats `0` as "menu" |
| Offhook Auto-Dial Delay | 0 | |
| **Disable Call-Waiting** | Yes | |
| Disable Call-Waiting Tone | Yes | |
| Send Anonymous | No | |
| Anonymous Call Rejection | No | the backend does whitelisting |
| Outgoing / Incoming Call Duration Limit | 0 | the backend enforces the cap with a friendly goodbye; a hard ATA cut-off would be a silent click |
| Enable Receiver Offhook Tone | No | the toddler will leave it off-hook; a howler tone is scary. The backend's "off-hook too long" notification covers this. |
| Enable Visual MWI | No | |
| Ring Timeout | 60 | Asterisk cancels earlier anyway |

Hook Flash group (same page): **Send Hook Flash Event** No, **Flash Digit Control** No,
**Callee Flash to 3WC** No.

## 7. FXS Port → Call Features Settings

Set every star-code feature (Call Forward *72, Do Not Disturb *78, Call Waiting *70, Blind
Transfer *87, Forced PCMU *027110, Disable LEC *03, Set Offhook Auto-Dial *77, Play Registration
ID *98, 3-way conference, etc.) to **disabled**, and **Disable Bellcore Style 3-Way Conference**
Yes. With dial plan `{x}` the ATA can't even collect `*7…`, but belt and braces: a toddler on `*`
should hear "that's not a number" from the backend, not program the ATA.

## 8. Advanced Settings

| Setting | Value |
|---------|-------|
| System Ring Cadence | `c=2000/4000;` (North American default; leave unless you want a shorter ring) |
| CPT Settings | leave at North American defaults |
| NTP Server | `pool.ntp.org` (timestamps in the ATA syslog) |
| Syslog Server / Level | `<pi-ip>`, INFO, only while debugging |
| Web Access | HTTP on LAN only; disable WAN-side access if the option exists; never port-forward it |

Click **Save and Apply** (V2) or **Update** then **Apply** (V1). Some changes need **Reboot**.

## 9. Verify

On the Pi:

```
docker compose exec asterisk asterisk -rx "pjsip show endpoints"
```

You want:

```
 Endpoint:  phone                                                Not in use    0 of inf
     InAuth:  phone-auth/phone
        Aor:  phone                                              1
      Contact:  phone/sip:phone@192.168.1.31:5060               a1b2c3d4e5 Avail        12.345
```

`pjsip show contacts` should list the same contact with status `Avail` and an RTT. If it says
`Unavail` the ATA registered but isn't answering OPTIONS (firewall on the Pi?). If the endpoint
has no contact at all, watch the registration attempt live:

```
docker compose exec asterisk asterisk -rx "pjsip set logger on"
docker compose logs -f asterisk | grep -E "REGISTER|401|403|200 OK"
```

- `401` then `200 OK` = good. `401` then `401` again = password mismatch (`PHONE_SIP_PASSWORD`
  vs Authenticate Password). `403` = wrong user id or the endpoint's `auth` section is missing.
- Nothing at all = ATA can't reach the Pi (IP typo, VLAN, Pi's firewall not allowing UDP 5060).

Then the physical test: lift the handset. Dial tone means registered (the HT801 says "device not
registered" through the earpiece otherwise). Press `7`. Within a second you should hear the fun
fact (roadmap M1). From the parent UI, press "test call": the phone rings.

The corresponding Asterisk side, for reference (the real file is templated in `asterisk/`):

```
[phone]
type=endpoint
context=from-phone
disallow=all
allow=ulaw
allow=alaw
dtmf_mode=rfc4733
direct_media=no
rtp_timeout=60
auth=phone-auth
aors=phone

[phone-auth]
type=auth
auth_type=userpass
username=phone
password=${PHONE_SIP_PASSWORD}

[phone]
type=aor
max_contacts=1
remove_existing=yes
qualify_frequency=30
```

## 10. Factory reset (if you lock yourself out)

Hold the reset pinhole for 7 s with Ethernet unplugged, or lift the handset, dial `***`, `99`,
then the MAC address encoded as digits (the guide has the letter→digit table: A=22, B=222, C=2222,
D=33, E=333, F=3333). The V2 goes back to the sticker password.
