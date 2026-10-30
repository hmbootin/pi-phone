# 0001 Raspberry Pi 4 runs everything

Status: accepted. 2026-10-29.

The Pico 2 W can't do SIP, codecs, TTS, a web app, and recording. A Raspberry Pi 4 (4 GB, 64-bit
Raspberry Pi OS Lite) can run Asterisk, the backend, and Piper TTS with room to spare, has wired
Ethernet (important: RTP over Wi-Fi is where jitter comes from), and has a huge Asterisk community.
A Pi 5 or any x86 mini PC works the same; nothing here is Pi-specific beyond `arm64` images.

Storage: boot from a USB SSD if possible. SD cards die under constant writes and these recordings
are memories. The backup job exists for the day the SSD dies too.
