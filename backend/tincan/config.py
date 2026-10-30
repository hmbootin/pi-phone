"""Runtime configuration from environment variables (see backend/README.md)."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Config(BaseSettings):
    """Each field maps to the upper-cased env var of the same name (TINCAN_DATA_DIR, ARI_URL)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tincan_data_dir: Path = Path("./data")
    tincan_host: str = "0.0.0.0"
    tincan_port: int = 8080
    tincan_parent_password: str = "tincan"
    tincan_secret_key: str = ""
    tincan_ui_dir: Path | None = None
    tincan_fake_ari: bool = False
    tincan_version: str = "dev"
    # Multiplies every call timer (ring timeout, time cap, warning). Only for tests and
    # `mise run dev`; 1.0 in production.
    tincan_time_scale: float = 1.0
    # Where ARI stored recordings land on the shared /data mount. Asterisk always writes them to
    # <astspooldir>/recording, and asterisk/etc/asterisk.conf sets astspooldir=/data/asterisk.
    tincan_recordings_dir: Path | None = None

    ari_url: str = "http://localhost:8088"
    ari_user: str = "tincan"
    ari_password: str = "tincan"
    ari_app: str = "tincan"

    piper_bin: str = "piper"
    piper_voice: str = "en_US-lessac-medium"
    piper_data_dir: Path | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    @property
    def data_dir(self) -> Path:
        return self.tincan_data_dir

    @property
    def recordings_dir(self) -> Path:
        return self.tincan_recordings_dir or (self.data_dir / "asterisk" / "recording")

    @property
    def prompts_dir(self) -> Path:
        return self.data_dir / "prompts"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "tincan.db"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.recordings_dir, self.prompts_dir):
            d.mkdir(parents=True, exist_ok=True)

    def secret_key(self) -> str:
        """TINCAN_SECRET_KEY, or a key generated once and kept in the data dir."""
        if self.tincan_secret_key:
            return self.tincan_secret_key
        path = self.data_dir / "secret_key"
        if path.exists():
            return path.read_text().strip()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        key = secrets.token_urlsafe(32)
        path.write_text(key)
        return key

    def warn_insecure(self) -> None:
        if self.tincan_parent_password == "tincan":
            log.warning(
                "TINCAN_PARENT_PASSWORD is the default 'tincan'; set it before exposing the UI"
            )
