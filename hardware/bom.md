# Bill of materials

Prices are US street as of late October 2026. Raspberry Pi prices jumped twice in 2026 because of
the DRAM shortage; check before ordering. The phone is already sourced (a line-powered big-button
corded phone, board `LD-858SOSBMB`); the parts to connect it to the Pi are in
[phone-interface.md](phone-interface.md) §4 and summarised here.

## Compute

| # | Item | Why | Price | Where | Have? |
|---|------|-----|-------|-------|-------|
| 1 | **Raspberry Pi 4 Model B, 4 GB** | Runs Asterisk, baresip, the backend and Piper. 2 GB also works. The Pi 4's headphone jack is what drives the ringer, so a Pi 5 or Zero would need a second USB audio adapter. | **$100** (4 GB) / $67.50 (2 GB) | [PiShop](https://www.pishop.us/product-category/raspberry-pi/raspberry-pi-boards/current-pi-boards/) | **yes** |
| 2 | Official 15 W USB-C power supply | Powers the Pi, the USB audio adapter and the ringer amp. Under-voltage = SD corruption. | **$8.80** | [PiShop](https://www.pishop.us/product/raspberry-pi-15w-power-supply-us-black/) | |
| 3 | Storage: **USB 3.0 SSD** (ADR 0001), e.g. a no-name 256 GB USB SSD, or Samsung T7 500 GB | Recordings are constant writes; SD cards die. 1 MB/min of audio means 256 GB is decades. | $30-40 (no-name) / ~$105 (T7) | | |
|   | *budget*: SanDisk High Endurance 64 GB microSD | If you accept the backup job as your safety net. | **~$15-19** | | |
| 4 | Cat 6 Ethernet patch cable | RTP over Wi-Fi is where drops come from. | **$2-5** | any | probably |
| 5 | Case or standoffs | The Pi sits beside the phone (or inside the base if the cavity fits; measure). A fan case is unnecessary at this load. | $0-15 | | |

## Phone interface (from phone-interface.md §4)

| # | Item | Qty | Price |
|---|------|-----|-------|
| 6 | USB audio adapter, separate mic + headphone jacks (CM108/CM119) | 1 | $8-12 |
| 7 | 3.5 mm male TRS screw-terminal plugs | pack of 5 | $6 |
| 8 | PAM8403 amplifier module with 3.5 mm input socket | 1 | $3-7 |
| 9 | Female-to-male jumper wires | 1 pack | $5 |
| 10 | 1 kΩ resistors | 15 | $3 or have |
| 11 | 40-pin GPIO ribbon + breadboard breakout | 1 | $7-10 |
| 12 | Solder wick / desoldering pump | 1 | $5 |
| 13 | 3.5 mm aux cable (scavenge) | 1 | $0 |

Measurement-gated extras (small 8 Ω speaker, MCP23017 expander): see phone-interface.md §4.

## Totals

| Build | Cost |
|-------|------|
| Already have the Pi 4 and the phone | interface parts + PSU + SD ≈ **$60-70** |
| From scratch with a USB SSD | Pi $100 + PSU $9 + SSD $35 + cable $4 + interface $40 ≈ **$190** |

Plus recurring: phone number ~$1-2/mo, E911 $0.75-1.50/mo, calls ~$0.01/min, Backblaze B2 for
backups ~$0.006/GB/mo (free under 10 GB). See
[docs/research/voip-providers.md](../docs/research/voip-providers.md).

Toddler-proofing: the coiled handset cord is the first thing to break. Buy one spare ($5). The
cable bundle to the Pi leaves through the old RJ11 hole; hot-glue it there so it cannot be pulled.
