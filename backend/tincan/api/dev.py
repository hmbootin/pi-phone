"""Dev-only: drive the fake Asterisk from the UI or curl. Mounted only when TINCAN_FAKE_ARI=1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from tincan.api.deps import ApiError, runtime

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/simulate")
async def simulate(body: dict[str, Any], request: Request) -> dict:
    rt = runtime(request)
    fake = rt.fake
    if fake is None:
        raise ApiError(404, "not_found", "fake ARI is off")
    event = body.get("event")
    if event == "offhook_dial":
        digit = str(body.get("digit", ""))
        cid = fake.emit_stasis_start(["dial", digit])
        return {"channel": cid}
    if event == "inbound":
        cid = fake.emit_stasis_start(
            ["inbound"], caller=body.get("from"), name_prefix="PJSIP/trunk"
        )
        return {"channel": cid}
    if event == "hangup":
        for cid in list(fake.channels):
            fake.hangup_channel(cid)
        return {"hung_up": True}
    if event == "answer":
        for cid, ch in list(fake.channels.items()):
            if ch.state == "Ringing":
                fake.answer_originated(cid)
        return {"answered": True}
    raise ApiError(400, "bad_event", "event must be offhook_dial, inbound, answer or hangup")
