"""Dev-only: drive the fake Asterisk and the fake phone hardware from the UI or curl.

Mounted only when TINCAN_FAKE_ARI=1. The hardware events (offhook, onhook, key) need
TINCAN_HARDWARE=fake as well; the ARI-level events work without it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from tincan.api.deps import ApiError, runtime
from tincan.hardware.keys import ALL_KEYS

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/simulate")
async def simulate(body: dict[str, Any], request: Request) -> dict:
    rt = runtime(request)
    fake = rt.fake
    if fake is None:
        raise ApiError(404, "not_found", "fake ARI is off")
    event = body.get("event")
    if event in ("offhook", "onhook", "key"):
        machine = rt.phone
        if machine is None or not hasattr(machine.inputs, "press"):
            raise ApiError(404, "not_found", "fake hardware is off (TINCAN_HARDWARE=fake)")
        if event == "offhook":
            machine.inputs.lift()
        elif event == "onhook":
            machine.inputs.hang_up()
        else:
            key = str(body.get("key", "")).lower()
            if key not in ALL_KEYS:
                raise ApiError(400, "bad_key", f"key must be one of {', '.join(ALL_KEYS)}")
            machine.inputs.press(key)
        return {"state": machine.state.value}
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
    raise ApiError(
        400,
        "bad_event",
        "event must be offhook, onhook, key, offhook_dial, inbound, answer or hangup",
    )
