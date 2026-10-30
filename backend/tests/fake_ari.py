"""Test-facing wrapper around the in-process fake ARI (tincan.ari.fake.FakeAri).

The fake itself lives in the package so `TINCAN_FAKE_ARI=1` can use it; this module adds the
assertion helpers tests read best.
"""

from __future__ import annotations

from tincan.ari.fake import CAUSE_BUSY, CAUSE_NO_ANSWER, CAUSE_NORMAL, FakeAri

__all__ = ["CAUSE_BUSY", "CAUSE_NO_ANSWER", "CAUSE_NORMAL", "FakeAri", "TestAri"]


class TestAri(FakeAri):
    __test__ = False  # not a pytest collection target

    # -- driving the phone ----------------------------------------------------------------------

    def dial(self, digit: str) -> str:
        """Toddler lifts the handset and presses `digit`."""
        return self.emit_stasis_start(["dial", digit])

    def inbound(self, caller: str) -> str:
        """The trunk delivers a call from `caller`."""
        return self.emit_stasis_start(["inbound"], caller=caller, name_prefix="PJSIP/trunk")

    def hangup_all(self) -> None:
        for cid in list(self.channels):
            self.hangup_channel(cid)

    def ringing_channels(self) -> list[str]:
        return [c.id for c in self.channels.values() if c.state == "Ringing"]

    # -- assertions -----------------------------------------------------------------------------

    def originated_endpoints(self) -> list[str]:
        return [o["endpoint"] for o in self.originates]

    def played_prompt_texts(self, tts) -> list[str]:
        """Map played media back to prompt texts via the TTS cache (reverse lookup)."""
        by_name = {tts.cache_name(t): t for t in tts.rendered}
        out = []
        for media in self.played_media():
            name = media.rsplit("/", 1)[-1]
            out.append(by_name.get(name, name))
        return out
