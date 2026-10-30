"""kind -> Feature instance. Add a line here when you add a feature."""

from __future__ import annotations

from typing import Any

from tincan.features.base import Feature
from tincan.features.fun_fact import FunFactFeature
from tincan.features.mailbox import MailboxFeature
from tincan.features.secret_message import SecretMessageFeature
from tincan.features.weather import WeatherFeature
from tincan.tts import prompts


class SongFeature(Feature):
    kind = "song"

    async def text(self, rt: Any, config: dict[str, Any]) -> str:
        return config.get("text") or prompts.SONG


class NoneFeature(Feature):
    kind = "none"

    async def text(self, rt: Any, config: dict[str, Any]) -> str:
        return prompts.NOTHING_THERE


FEATURES: dict[str, Feature] = {
    f.kind: f
    for f in (
        WeatherFeature(),
        FunFactFeature(),
        SecretMessageFeature(),
        MailboxFeature(),
        SongFeature(),
        NoneFeature(),
    )
}


def get_feature(kind: str) -> Feature | None:
    return FEATURES.get(kind)
