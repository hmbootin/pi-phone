# 0005 One repo, one toolchain entry point, Docker on the Pi

Status: accepted. 2026-10-29.

Hardware docs, firmware, backend, UI, and deployment live together so one PR can change a feature
end to end. `mise` at the repo root pins toolchains (python, uv, node, pnpm) and exposes the tasks
developers run; each package has its own native tooling underneath (`uv`, `pnpm`).

On the Pi, everything is Docker Compose: `asterisk`, `backend` (which serves the built UI), and a
`backup` sidecar. Images are built by GitHub Actions for `linux/arm64` on every tag and pulled by
the Pi. Host-level things (Tailscale, Docker, the data directory, a systemd timer that pulls
updates) are set up once by `deploy/bootstrap.sh`.

Why containers on a Pi: Asterisk builds are painful to reproduce by hand, and "it works on my Pi"
should be a tag, not a snowflake. The cost is a slower first pull; it's a home server.
