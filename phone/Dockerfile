# syntax=docker/dockerfile:1.7
#
# baresip for Tin Can: the "phone" Compose service. It turns the handset's USB audio adapter into
# a SIP phone that registers to the Asterisk container as endpoint "phone" and takes orders from
# the backend over the ctrl_tcp module (see README.md for the wire protocol).
#
# Distro package, not a source build. Debian trixie ships baresip-core 1.1.0 (2021) for amd64 and
# arm64 with every module we need already compiled in: ctrl_tcp, alsa, g711, account, menu
# (which owns the dial/accept/hangup commands), aufile/ausine/auloop for no-hardware tests.
# Alpine stable has no baresip at all (only edge/testing), bookworm and Ubuntu noble have 1.0.0.
# 1.1.0 is old but it is the newest pinnable package; the ctrl_tcp protocol has not changed
# shape since, so moving to a source build of 3.x later is a Dockerfile-only change.
#
# The image builds in well under a minute on any arch, which is why CI builds it on every PR.

ARG DEBIAN_IMAGE=debian:trixie-slim

FROM ${DEBIAN_IMAGE}
LABEL org.opencontainers.image.title="tincan-phone" \
      org.opencontainers.image.description="baresip SIP phone for the Tin Can toddler landline" \
      org.opencontainers.image.source="https://github.com/hmbootin/pi-phone"

ENV DEBIAN_FRONTEND=noninteractive
# baresip-core: the binary plus every module (no GUI). gettext-base: envsubst for the entrypoint.
# alsa-utils: aplay/arecord/alsamixer for troubleshooting the USB adapter from inside the
# container. tini reaps and forwards signals so `docker stop` ends baresip cleanly.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    baresip-core gettext-base alsa-utils tini ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    # Runs unprivileged. gid 29 is "audio" on Debian and Raspberry Pi OS, which owns /dev/snd.
    && groupadd -r -g 2001 phone \
    && useradd -r -u 2001 -g phone -G audio -d /var/lib/phone -s /usr/sbin/nologin phone \
    && mkdir -p /etc/baresip /var/lib/phone \
    && chown -R phone:phone /etc/baresip /var/lib/phone

# Templates rendered to /etc/baresip/{config,accounts} by the entrypoint at every start.
COPY etc/ /etc/baresip/
COPY entrypoint.sh healthcheck.sh /usr/local/bin/
RUN chmod 0755 /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh \
    && chown -R phone:phone /etc/baresip

USER 2001
WORKDIR /var/lib/phone

# Informational: compose runs this with network_mode: host. 5062/udp is SIP (Asterisk owns
# 5060 on the same host), 4444/tcp is ctrl_tcp.
EXPOSE 5062/udp 4444/tcp

# Checks the ctrl_tcp listener exists WITHOUT connecting to it: ctrl_tcp accepts exactly one
# client and drops the previous one on a new connect, so a probing healthcheck would knock the
# backend off every interval.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
