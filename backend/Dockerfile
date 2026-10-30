# Tin Can backend image. Build from the REPO ROOT:
#
#   docker build -f backend/Dockerfile -t tincan-backend .                      # API only
#   docker build -f backend/Dockerfile --build-arg UI_DIST=local -t tincan-backend .   # with ui/dist
#
# CI builds ui/dist first and passes UI_DIST=local. The default (empty) keeps local builds working
# when ui/dist does not exist: BuildKit only evaluates the stage that FROM ui-${UI_DIST} selects.
ARG UI_DIST=empty
ARG PYTHON_VERSION=3.12

# ---- UI: pick "local" (COPY ui/dist) or "empty" (nothing) ----------------------------------------
FROM alpine:3.20 AS ui-empty
RUN mkdir -p /dist

FROM alpine:3.20 AS ui-local
COPY ui/dist /dist

FROM ui-${UI_DIST} AS ui-dist

# ---- Python deps --------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/tincan ./tincan
RUN uv sync --frozen --no-dev

# Piper TTS (abi3 wheels exist for arm64 and amd64). The voice is fetched at build time so the
# image is self-contained (~65 MB for en_US-lessac-medium). If the download fails the build still
# succeeds and the backend falls back to a beep; mount a voice at /opt/piper/voices instead.
ARG PIPER_VOICE=en_US-lessac-medium
RUN uv pip install --python /app/.venv/bin/python "piper-tts>=1.3" \
 && mkdir -p /opt/piper/voices \
 && (/app/.venv/bin/python -m piper.download_voices "${PIPER_VOICE}" --data-dir /opt/piper/voices \
     || echo "WARNING: piper voice download failed; mount /opt/piper/voices at runtime")

# ---- Runtime ------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm
RUN useradd --create-home --uid 1000 tincan && mkdir -p /data && chown tincan:tincan /data
WORKDIR /app
COPY --from=builder /app /app
COPY --from=builder /opt/piper /opt/piper
COPY --from=ui-dist /dist /app/ui
ENV PATH="/app/.venv/bin:$PATH" \
    TINCAN_DATA_DIR=/data \
    TINCAN_UI_DIR=/app/ui \
    PIPER_BIN=/app/.venv/bin/piper \
    PIPER_VOICE=en_US-lessac-medium \
    PIPER_DATA_DIR=/opt/piper/voices \
    TINCAN_HOST=0.0.0.0 \
    TINCAN_PORT=8080
USER tincan
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')" || exit 1
CMD ["tincan", "serve"]
