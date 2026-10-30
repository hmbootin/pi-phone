# Bill of materials (v1)

Prices are US list/street as of late October 2026, from the linked pages. Raspberry Pi prices
jumped twice in 2026 because of the DRAM shortage; check before ordering. Everything except the
Pi and the ATA is interchangeable with whatever you have in a drawer.

## Core

| # | Item | Why | Price | Where | Have? |
|---|------|-----|-------|-------|-------|
| 1 | **Raspberry Pi 4 Model B, 4 GB** | Runs Asterisk + backend + Piper. 2 GB also works (Asterisk + backend use ~500 MB; Piper peaks ~300 MB). | **$100** (4 GB) / $67.50 (2 GB) | [PiShop](https://www.pishop.us/product-category/raspberry-pi/raspberry-pi-boards/current-pi-boards/), [Phoronix on the Oct 2026 hike](https://www.phoronix.com/news/Raspberry-Pi-5-2GB-Price-77.50) | |
|   | *or* Raspberry Pi 5, 4 GB | Same software; faster; needs 27 W PSU and its own case/cooler. Only $10 more than the Pi 4 right now, so buy this if starting from zero. | $110 (4 GB) / $77.50 (2 GB) | same | |
| 2 | Official 15 W USB-C power supply (Pi 4) | Under-voltage = SD corruption and USB SSD dropouts. Don't use a phone charger. | **$8.80** | [PiShop](https://www.pishop.us/product/raspberry-pi-15w-power-supply-us-black/) | |
|   | *or* official 27 W USB-C (Pi 5) | | ~$12-14 (not verified this week) | PiShop / Micro Center | |
| 3 | Case with fan: **Argon ONE V2** (Pi 4) | Aluminium, fan, power button, all ports on the back. Any fan case works; the Pi runs warm transcoding + TTS. | **$25** | [argon40.com](https://argon40.com/products/argon-one-v2-case-for-raspberry-pi-4) | |
|   | cheaper: 52Pi/GeeekPi fan case | | $13-19 | Walmart/Amazon (price varies) | |
|   | Pi 5: official case + Active Cooler | | ~$10 + $5 (not verified this week) | PiShop | |
| 4 | Storage: **USB 3.0 SSD** (ADR 0001) e.g. Samsung T7 500 GB, or any 2.5" SATA SSD in a $10 USB enclosure | Recordings are constant writes; SD cards die. 1 MB/min of audio means 500 GB is decades. | T7 500 GB **~$105** (inflated by the NAND shortage); a no-name 256 GB USB SSD is ~$30-40 | [Samsung](https://www.samsung.com/us/memory-storage/portable-ssd/portable-ssd-t7-touch-usb-3-2-500gb-black-sku-mu-pc500k-ww/) | |
|   | *budget*: SanDisk High Endurance 64 GB microSD | If you accept the backup job as your safety net. "High Endurance" (dashcam) cards survive far longer than normal ones. | **~$15-19** | [various](https://deploydepot.ca/products/sandisk-high-endurance-64-gb-microsd-sdsqqnr-064g-gn6ia) | |
| 5 | Cat 6 Ethernet patch cable ×2 (Pi, ATA) | RTP over Wi-Fi is where drops come from. | **$2-5 each** | any | probably |
| 6 | **Grandstream HT801 V2** (1 FXS port ATA) | The analog line. V1 is discontinued; V2 is the same hardware with a new web UI and a per-unit random password. Supports pulse dialing. | **$33-38** street, $55 MSRP | [Streakwave $33](https://www.streakwave.com/grandstream-networks-ht801-handytone-801-ht801-ata-1-fxs-port), [IP Phone Warehouse $37.99](https://www.ipphone-warehouse.com/grandstream-ht801-v2-1-port-ata-analog-telephone-adapter/), [VoIP Supply](https://www.voipsupply.com/grandstream-ht801-ata) | |
|   | *alt*: Grandstream HT802 V2 (2 FXS) | Only if you want a second phone (sibling, parents' handset). Config identical. | $39-46 | [IP Phone Warehouse](https://www.ipphone-warehouse.com/grandstream-ht802-v2-2-port-ata-analog-telephone-adapter/) | |
|   | *alt*: Cisco ATA 191 / 192 | Solid but enterprise-priced and the web UI is worse. Prices all over the map ($65 clearance to $199+). | $65-265 | [VoIP Supply](https://www.voipsupply.com/catalogsearch/result/index/?q=ata) | |
|   | *avoid*: Obihai OBi200/OBi202 | **End of life**: production ended Dec 2021, support ended Dec 2023, the OBiTALK provisioning portal shut down Oct 2024. Used ones still register to Asterisk, but no firmware and no support. | used $20-40 | eBay | |
| 7 | RJ11 phone cord, 7 ft | ATA → phone. Most phones include one. | **$3** | [C2G at CDW](https://www.cdw.com/product/c2g-7ft-rj11-mod-telephone-cable/1838708) | probably |
| 8 | **Corded landline phone** (see below) | The toddler's half. | **$15-50** | | |

## The phone

Requirements: corded (no batteries, no base station pairing), DTMF keypad (every phone made after
1985), big buttons, a real bell or loud ringer, cheap enough to be chewed. No need for caller ID,
speakerphone or an answering machine; those are fine but unused. Pulse-only is not required
because the HT801 supports it anyway.

| Model | Why | Price | Link |
|-------|-----|-------|------|
| **AT&T CL2940** | Extra-large buttons, tilt display, loud ringer, volume boost. The default pick. | **$47** (att.com $46.95; Walmart ~$51; Newegg ~$48) | [Amazon](https://www.amazon.com/AT-CL2940-waiting-Speakerphone-Display/dp/B009R5VTX6), [att.com](https://telephones.att.com/) |
| **VTech CD1113** | Cheapest decent corded phone, normal-size keys, caller ID. | **$15-22** | [Walmart](https://walmart.com/ip/Vtech-Cd1113-Corded-Phone-With-Caller-Id/240547510), [Zoro](https://www.zoro.com/vtech-vtech-cd1113-standard-phone-black-corded-corded-1-x-phone-line-cd1113/i/G810028727/) |
| AT&T CD4930 | Big buttons + speakerphone + answering machine (unneeded). Often out of stock. | ~$54 | [Walmart](https://www.walmart.com/ip/at-t-cd4930-corded-phone-with-answering-system-and-caller-id-black/387190452) |
| A thrift-store rotary or 1970s Trimline | The charming option. Rotary = pulse dialing: enable "Enable Pulse Dialing" on the HT801 (works, verified in the V2 admin guide). A real bell draws more ring current; set Ring Power to 55 Vrms. Clean the dial contacts. | $5-25 | Goodwill, eBay |

Toddler-proofing: a corded phone's handset cord is the first thing to break. Buy one spare coiled
handset cord ($5). Tape the RJ11 plug on the wall side so it can't be pulled.

## Optional

| Item | Why | Price | Have? |
|------|-----|-------|-------|
| **Raspberry Pi Pico 2 W** + buttons | Big "call Mom" arcade button or extra feature buttons, reporting to the backend over Wi-Fi (roadmap M4). Firmware in `firmware/pico/`. | $7 | **yes, owned** |
| Arcade button, 60 mm | For the above | $5 | |
| PoE splitter or a 2-port USB charger | The HT801 ships with its own 5 V adapter; a single multi-port charger tidies the shelf. | $10 | |
| v2 DIY line interface parts | See [diy-line-interface.md](diy-line-interface.md); not needed for v1. | ~$25 | |

## Totals

| Build | Items | Cost |
|-------|-------|------|
| **Recommended** | Pi 4 4 GB $100 + PSU $9 + Argon case $25 + 256 GB USB SSD ~$35 + cables $8 + HT801 V2 $35 + AT&T CL2940 $47 | **≈ $260** |
| Budget | Pi 4 2 GB $68 + PSU $9 + fan case $14 + High Endurance SD $17 + cables $8 + HT801 V2 $35 + VTech CD1113 $18 | **≈ $170** |
| Already have a Pi 4 and a phone | HT801 V2 + cables | **≈ $40** |

Plus recurring: phone number ~$1-2/mo, E911 $0.75-1.50/mo, calls ~$0.01/min, Backblaze B2 for
backups ~$0.006/GB/mo (free under 10 GB). See
[docs/research/voip-providers.md](../docs/research/voip-providers.md).
