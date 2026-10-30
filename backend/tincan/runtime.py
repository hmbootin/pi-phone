"""Everything the app shares at runtime: config, db, ARI, TTS, notifier, broadcaster, router."""

from __future__ import annotations

import logging
from typing import Any

from tincan import store
from tincan.ari.client import AriClient
from tincan.ari.fake import FakeAri
from tincan.calls.router import CallRouter
from tincan.config import Config
from tincan.db import Database
from tincan.events import Broadcaster
from tincan.features import FEATURES
from tincan.hardware.machine import PhoneStateMachine
from tincan.hardware.sounds import SoundSet
from tincan.notify import Notifier
from tincan.schemas import CallOut, Settings
from tincan.tts.piper import Tts

log = logging.getLogger(__name__)


class Runtime:
    def __init__(self, config: Config):
        self.config = config
        config.ensure_dirs()
        self.db = Database(config.db_path)
        self.db.migrate()
        self.events = Broadcaster()
        self.tts = Tts(
            config.prompts_dir, config.piper_bin, config.piper_voice, config.piper_data_dir
        )
        self.notifier = Notifier(config)
        self.features = FEATURES
        self.ari_connected = False
        self.fake: FakeAri | None = None
        if config.tincan_fake_ari:
            self.fake = FakeAri(recordings_dir=config.recordings_dir)
            self.ari: Any = self.fake
            log.warning("TINCAN_FAKE_ARI=1: using the in-process fake Asterisk")
        else:
            self.ari = AriClient(
                config.ari_url, config.ari_user, config.ari_password, config.ari_app
            )
        self.router = CallRouter(self)
        self.phone: PhoneStateMachine | None = self._build_phone()
        self._started = False

    def _build_phone(self) -> PhoneStateMachine | None:
        """The phone-side state machine over real or fake hardware, or None when no phone."""
        config = self.config
        if config.tincan_hardware == "none":
            return None
        if config.tincan_hardware == "fake":
            from tincan.hardware.fake import FakeAudio, FakeInputs, FakePhone

            inputs: Any = FakeInputs()
            audio: Any = FakeAudio()
            phone: Any = FakePhone(ari=self.fake)
            log.warning("TINCAN_HARDWARE=fake: using in-process keypad/hook/audio/baresip")
        else:
            from tincan.hardware import pinmap
            from tincan.hardware.alsa import AlsaAudio
            from tincan.hardware.baresip import BaresipClient
            from tincan.hardware.gpio import GpioInputs

            inputs = GpioInputs(pinmap.load(config.tincan_pinmap or pinmap.DEFAULT_PATH))
            audio = AlsaAudio(
                config.handset_audio_device, config.ringer_audio_device, config.ringer_mixer
            )
            phone = BaresipClient(config.phone_ctrl_host, config.phone_ctrl_port)
        return PhoneStateMachine(
            inputs,
            audio,
            phone,
            SoundSet.default(),
            sip_host=config.asterisk_sip_host,
            publish=self.events.publish,
            ringer_volume=lambda: getattr(self.settings(), "ringer_volume", 80),
        )

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        await self.router.start()
        if self.phone is not None:
            await self.phone.start()

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        if self.phone is not None:
            await self.phone.stop()
            for part in (self.phone.inputs, self.phone.audio, self.phone.phone):
                await part.close()
        await self.router.stop()
        await self.ari.close()

    def settings(self) -> Settings:
        return store.get_settings(self.db)

    def call_json(self, call_id: int) -> dict[str, Any]:
        with self.db.session() as s:
            from tincan.models import Call

            call = s.get(Call, call_id)
            return CallOut.from_row(call).model_dump() if call else {"id": call_id}

    async def notify(self, title: str, message: str, url: str | None = None) -> None:
        await self.notifier.send(self.settings().notifications, title, message, url)
