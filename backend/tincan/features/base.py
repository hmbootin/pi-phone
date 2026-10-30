"""A feature is what a non-contact digit does. Subclass, register in registry.py, add prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tincan.calls.session import CallSession
    from tincan.runtime import Runtime


class Feature:
    kind = "none"

    async def text(self, rt: Runtime, config: dict[str, Any]) -> str:
        """What the feature would say; used by the parent UI preview and by the default run()."""
        raise NotImplementedError

    async def run(self, session: CallSession, config: dict[str, Any]) -> None:
        """Called with the phone channel answered. Default: say text() and finish."""
        await session.say(await self.text(session.rt, config))
