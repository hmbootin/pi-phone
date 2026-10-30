"""Play unlistened voicemails left for the toddler by known contacts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tincan import store
from tincan.features.base import Feature
from tincan.tts import prompts

if TYPE_CHECKING:
    from tincan.calls.session import CallSession
    from tincan.runtime import Runtime


class MailboxFeature(Feature):
    kind = "mailbox"

    async def text(self, rt: Runtime, config: dict[str, Any]) -> str:
        n = len(store.unlistened_for_toddler(rt.db))
        return prompts.MAILBOX_EMPTY if n == 0 else prompts.MAILBOX_INTRO.format(count=n)

    async def run(self, session: CallSession, config: dict[str, Any]) -> None:
        rt = session.rt
        pending = store.unlistened_for_toddler(rt.db)
        if not pending:
            await session.say(prompts.MAILBOX_EMPTY)
            return
        await session.say(prompts.MAILBOX_INTRO.format(count=len(pending)))
        for rec in pending:
            contact = store.contact_by_id(rt.db, rec.contact_id)
            await session.say(
                prompts.MAILBOX_FROM.format(name=contact.spoken_name if contact else "someone")
            )
            path = (rt.config.recordings_dir / rec.path).with_suffix("")
            await session.play(f"sound:{path}")
            store.mark_listened(rt.db, rec.id)
        await session.say(prompts.MAILBOX_DONE)
