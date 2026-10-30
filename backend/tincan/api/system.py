from __future__ import annotations

import shutil

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from tincan import __version__, backup, store
from tincan.api.deps import ApiError, runtime
from tincan.schemas import BackupReportIn, BackupStatus, SystemStatus, TestCallIn

router = APIRouter(prefix="/api", tags=["system"])


async def _endpoint_state(rt, name: str) -> str | None:
    if not rt.ari_connected:
        return None
    try:
        ep = await rt.ari.get_endpoint("PJSIP", name)
    except Exception:  # noqa: BLE001
        return None
    return None if ep is None else ep.get("state", "unknown")


@router.get("/system/status")
async def status(request: Request) -> SystemStatus:
    rt = runtime(request)
    phone = await _endpoint_state(rt, "phone")
    trunk = await _endpoint_state(rt, "trunk")
    usage = shutil.disk_usage(rt.config.data_dir)
    return SystemStatus(
        asterisk="connected" if rt.ari_connected else "disconnected",
        phone="registered" if phone == "online" else "unregistered",
        # ARI reports endpoint state from qualify/contacts; outbound registration state is not
        # exposed through ARI, so "registered" here means the endpoint exists and is reachable.
        trunk="unconfigured"
        if trunk is None
        else ("registered" if trunk == "online" else "unregistered"),
        version=rt.config.tincan_version if rt.config.tincan_version != "dev" else __version__,
        disk_free_bytes=usage.free,
        backup=BackupStatus(last_ok_at=backup.last_ok(rt.db), pending=len(backup.pending(rt.db))),
    )


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    rt = runtime(request)
    return StreamingResponse(
        rt.events.subscribe(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/system/test-call", status_code=202)
async def test_call(body: TestCallIn, request: Request) -> dict:
    rt = runtime(request)
    contact = store.contact_by_id(rt.db, body.contact_id)
    if body.contact_id is not None and contact is None:
        raise ApiError(404, "not_found", f"No contact {body.contact_id}")
    try:
        call_id = await rt.router.start_test_call(contact)
    except RuntimeError as exc:
        raise ApiError(409, "line_busy", str(exc)) from exc
    return {"call_id": call_id}


@router.get("/system/backup/pending")
async def backup_pending(request: Request) -> list[dict]:
    rt = runtime(request)
    return [{"id": r.id, "path": r.path, "sha256": r.sha256} for r in backup.pending(rt.db)]


@router.post("/system/backup-report")
async def backup_report(body: BackupReportIn, request: Request) -> dict:
    rt = runtime(request)
    n = backup.mark_done(rt.db, body.ids, ok=body.ok)
    return {"marked": n}
