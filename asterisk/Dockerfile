# syntax=docker/dockerfile:1.7
#
# Asterisk 20 LTS for Tin Can, built from source on Debian bookworm.
#
# Why build from source instead of `andrius/asterisk` or `mlan/asterisk`:
#  - Neither publishes a current 20.x LTS for linux/arm64 that we control the module
#    list of; both ship every channel driver and a lot of sound packs we never load.
#  - Debian's `asterisk` package is 20.x but is a large dependency tree (chan_dahdi,
#    ODBC, LDAP...) and runs as a different user/path layout than we want.
#  - A pinned source build is reproducible: this file plus the version arg is the
#    whole story, which matters when "it works on my Pi" must be a tag (ADR 0005).
#
# The cost: a from-source build. Natively on arm64 (an Apple Silicon Mac, GitHub's
# ubuntu-24.04-arm runner, or the Pi) it takes minutes; under QEMU on an amd64 runner it
# takes ~40-60 min. .github/workflows/asterisk-image.yml builds and smoke-tests this file
# natively on every change (and weekly, so a retired upstream tarball is noticed);
# .github/workflows/release.yml publishes it. asterisk/etc/README.md has the local recipe.
#
# Multi-stage: the builder has compilers and -dev packages; the runtime image only has
# shared libraries, the installed Asterisk tree, and gettext for envsubst.

ARG ASTERISK_VERSION=20.21.0
ARG DEBIAN_IMAGE=debian:bookworm-slim

# ---------------------------------------------------------------- builder
FROM ${DEBIAN_IMAGE} AS builder
ARG ASTERISK_VERSION

ENV DEBIAN_FRONTEND=noninteractive
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl pkg-config \
    bzip2 patch \
    libedit-dev libjansson-dev libsqlite3-dev libssl-dev libxml2-dev \
    uuid-dev libsrtp2-dev libgsm1-dev \
    && rm -rf /var/lib/apt/lists/*
# bzip2 + patch: `./configure --with-pjproject-bundled` downloads pjproject as a .tar.bz2 and
# applies Asterisk's patches to it; bookworm-slim ships neither tool.

WORKDIR /usr/src
RUN curl -fsSL "https://downloads.asterisk.org/pub/telephony/asterisk/releases/asterisk-${ASTERISK_VERSION}.tar.gz" \
    -o asterisk.tar.gz \
    && tar xzf asterisk.tar.gz && rm asterisk.tar.gz \
    && mv "asterisk-${ASTERISK_VERSION}" asterisk

WORKDIR /usr/src/asterisk
# Bundled pjproject: Asterisk's own patched copy, the only supported option for chan_pjsip.
# --disable-xmldoc keeps the runtime from needing the XML docs tree.
RUN ./configure \
    --with-pjproject-bundled \
    --without-dahdi --without-pri --without-ss7 --without-x11 \
    --disable-xmldoc \
    --prefix=/usr --sysconfdir=/etc --localstatedir=/var \
    && make menuselect.makeopts

# Minimal module set. Start from "nothing", then enable exactly what Tin Can uses:
# chan_pjsip + the res_pjsip_* pieces it needs, ARI/Stasis, MixMonitor, playback, ulaw/alaw/gsm,
# wav. Every name below exists in 20.21.0; menuselect exits non-zero on an unknown module, so
# adding one is a build-time error, not a silent no-op. Anything added here must also be
# `load =>`ed in etc/modules.conf (autoload=no); asterisk/smoke-test.sh checks the two agree.
#
# --disable-all also clears the "Compiler Flags" category. That is what we want for
# BUILD_NATIVE (a Mac- or runner-tuned -march would not run on a Pi), but OPTIONAL_API must be
# turned back on: without it every `.optional_modules` reference (res_pjsip -> res_geolocation,
# res_statsd; app_mixmonitor -> func_periodic_hook; app_stack -> res_agi) becomes a hard symbol
# dependency, res_pjsip.so fails to dlopen, and chan_pjsip/ARI never come up.
RUN menuselect/menuselect \
    --disable-all \
    --enable OPTIONAL_API \
    --enable chan_pjsip \
    --enable res_pjproject --enable res_sorcery_config --enable res_sorcery_memory \
    --enable res_sorcery_astdb \
    --enable res_pjsip --enable res_pjsip_session --enable res_pjsip_sdp_rtp \
    --enable res_pjsip_outbound_registration --enable res_pjsip_registrar \
    --enable res_pjsip_authenticator_digest --enable res_pjsip_outbound_authenticator_digest \
    --enable res_pjsip_endpoint_identifier_ip --enable res_pjsip_endpoint_identifier_user \
    --enable res_pjsip_endpoint_identifier_anonymous \
    --enable res_pjsip_caller_id --enable res_pjsip_dtmf_info --enable res_pjsip_nat \
    --enable res_pjsip_rfc3326 --enable res_pjsip_refer --enable res_pjsip_header_funcs \
    --enable res_pjsip_notify --enable res_pjsip_pubsub --enable res_pjsip_logger \
    --enable res_pjsip_diversion --enable res_pjsip_path --enable res_pjsip_messaging \
    --enable res_pjsip_acl --enable res_pjsip_empty_info \
    --enable res_pjsip_exten_state --enable res_pjsip_mwi --enable res_pjsip_mwi_body_generator \
    --enable res_pjsip_pidf_body_generator --enable res_pjsip_dialog_info_body_generator \
    --enable res_rtp_asterisk --enable res_srtp \
    --enable res_http_websocket --enable res_crypto \
    --enable res_ari --enable res_ari_model --enable res_ari_applications \
    --enable res_ari_asterisk --enable res_ari_bridges --enable res_ari_channels \
    --enable res_ari_device_states --enable res_ari_endpoints --enable res_ari_events \
    --enable res_ari_playbacks --enable res_ari_recordings --enable res_ari_sounds \
    --enable res_stasis --enable res_stasis_answer --enable res_stasis_device_state \
    --enable res_stasis_playback --enable res_stasis_recording --enable res_stasis_snoop \
    --enable res_timing_timerfd --enable res_musiconhold --enable res_clioriginate \
    --enable bridge_simple --enable bridge_softmix --enable bridge_holding \
    --enable bridge_native_rtp --enable bridge_builtin_features \
    --enable bridge_builtin_interval_features \
    --enable app_stasis --enable app_mixmonitor --enable app_playback --enable app_dial \
    --enable app_echo --enable app_playtones --enable app_senddtmf --enable app_verbose \
    --enable app_stack --enable app_record --enable app_originate \
    --enable app_read \
    --enable func_callerid --enable func_channel --enable func_cdr --enable func_strings \
    --enable func_logic --enable func_math --enable func_global --enable func_cut \
    --enable func_env --enable func_timeout --enable func_pjsip_endpoint \
    --enable func_pjsip_contact --enable func_pjsip_aor --enable func_sorcery \
    --enable pbx_config --enable pbx_spool \
    --enable codec_ulaw --enable codec_alaw --enable codec_gsm --enable codec_a_mu \
    --enable codec_resample \
    --enable format_wav --enable format_wav_gsm --enable format_gsm --enable format_pcm \
    --enable format_sln \
    --enable cdr_custom --enable cel_custom --enable res_security_log --enable res_limit \
    --enable CORE-SOUNDS-EN-GSM \
    menuselect.makeopts

RUN make -j"$(nproc)" && make install DESTDIR=/opt/asterisk-root \
    && rm -rf /opt/asterisk-root/usr/include /opt/asterisk-root/usr/share/man \
    && mkdir -p /opt/asterisk-root/etc/asterisk \
    && rm -rf /opt/asterisk-root/var/run
# ^ `make install` creates var/run/asterisk, but in the runtime image /var/run is a symlink to
# /run and `COPY --from=builder / /` refuses to copy a directory over it. The runtime stage
# recreates /var/run/asterisk itself (and the entrypoint chowns it).

# ---------------------------------------------------------------- runtime
FROM ${DEBIAN_IMAGE} AS runtime
ARG ASTERISK_VERSION
LABEL org.opencontainers.image.title="tincan-asterisk" \
      org.opencontainers.image.description="Asterisk ${ASTERISK_VERSION} for the Tin Can toddler landline" \
      org.opencontainers.image.source="https://github.com/hmbootin/pi-phone"

ENV DEBIAN_FRONTEND=noninteractive
# gettext-base gives us envsubst; the rest are the shared libs the builder linked against.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext-base ca-certificates tini \
    libedit2 libjansson4 libsqlite3-0 libssl3 libxml2 libuuid1 libsrtp2-1 libgsm1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r -g 2000 asterisk \
    && useradd -r -u 2000 -g asterisk -d /var/lib/asterisk -s /usr/sbin/nologin asterisk

COPY --from=builder /opt/asterisk-root/ /

# Config templates and static config. The entrypoint renders *.conf.tmpl → *.conf at start.
COPY etc/ /etc/asterisk/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
    && mkdir -p /data/recordings /data/prompts /var/run/asterisk /var/log/asterisk /var/spool/asterisk /var/lib/asterisk \
    && chown -R asterisk:asterisk /etc/asterisk /var/run/asterisk /var/log/asterisk /var/spool/asterisk /var/lib/asterisk /data

VOLUME ["/data"]
# SIP signalling and the RTP range from rtp.conf. Informational only: compose runs this
# container with network_mode: host, so no port mapping happens.
EXPOSE 5060/udp 5060/tcp 8088/tcp 10000-10100/udp

# hadolint ignore=DL3025
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD asterisk -rx "core show uptime" >/dev/null 2>&1 || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
