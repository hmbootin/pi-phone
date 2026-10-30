from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select

from tincan import store
from tincan.api.deps import runtime
from tincan.models import Call
from tincan.schemas import CallOut

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("")
async def list_calls(
    request: Request, limit: int = Query(50, ge=1, le=500), before: int | None = None
) -> list[CallOut]:
    rt = runtime(request)
    with rt.db.session() as s:
        q = select(Call).order_by(Call.id.desc()).limit(limit)
        if before is not None:
            q = q.where(Call.id < before)
        return [CallOut.from_row(c) for c in s.scalars(q)]


@router.get("/active")
async def active_call(request: Request) -> CallOut | None:
    rt = runtime(request)
    active = rt.router.active
    if active is None:
        return None
    call = store.update_call(rt.db, active.call_id)
    return CallOut.from_row(call) if call else None


@router.post("/active/hangup", status_code=204)
async def hangup_active(request: Request) -> Response:
    await runtime(request).router.hangup_active()
    return Response(status_code=204)
