"""Record a message for a parent until the toddler hangs up, then notify."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tincan.features.base import Feature
from tincan.tts import prompts

if TYPE_CHECKING:
    from tincan.calls.session import CallSession
    from tincan.runtime import Runtime


class SecretMessageFeature(Feature):
    kind = "secret_message"

    async def text(self, rt: Runtime, config: dict[str, Any]) -> str:
        return prompts.SECRET_PROMPT.format(name=config.get("recipient", "Mom"))

    async def run(self, session: CallSession, config: dict[str, Any]) -> None:
        await session.say(await self.text(session.rt, config))
        await session.record_until_hangup(
            session.phone_channel or "", prefix="secret", kind="secret"
        )
        if session.recording_id:
            await session.rt.notify(
                "New secret message",
                f"A secret message for {config.get('recipient', 'Mom')} is waiting.",
                url=f"/api/recordings/{session.recording_id}/audio",
            )
            await session.say(prompts.SECRET_THANKS)
