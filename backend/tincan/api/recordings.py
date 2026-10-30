from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from tincan.api.deps import ApiError, runtime
from tincan.models import Recording
from tincan.schemas import RecordingOut, RecordingPatch

router = APIRouter(tags=["recordings"])


@router.get("/api/recordings")
async def list_recordings(
    request: Request,
    kind: str | None = None,
    contact_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    backed_up: bool | None = None,
) -> list[RecordingOut]:
    rt = runtime(request)
    with rt.db.session() as s:
        q = select(Recording).order_by(Recording.id.desc()).limit(limit)
        if kind:
            q = q.where(Recording.kind == kind)
        if contact_id is not None:
            q = q.where(Recording.contact_id == contact_id)
        if backed_up is True:
            q = q.where(Recording.backed_up_at.is_not(None))
        elif backed_up is False:
            q = q.where(Recording.backed_up_at.is_(None))
        return [RecordingOut.from_row(r) for r in s.scalars(q)]


@router.patch("/api/recordings/{recording_id}")
async def patch_recording(
    recording_id: int, body: RecordingPatch, request: Request
) -> RecordingOut:
    rt = runtime(request)
    with rt.db.session() as s:
        r = s.get(Recording, recording_id)
        if r is None:
            raise ApiError(404, "not_found", f"No recording {recording_id}")
        if body.listened is not None:
            r.listened = body.listened
        s.flush()
        return RecordingOut.from_row(r)


@router.get("/api/recordings/{recording_id}/audio")
async def recording_audio(recording_id: int, request: Request) -> Response:
    rt = runtime(request)
    with rt.db.session() as s:
        r = s.get(Recording, recording_id)
    if r is None:
        raise ApiError(404, "not_found", f"No recording {recording_id}")
    path = rt.config.recordings_dir / r.path
    if not path.exists():
        raise ApiError(404, "file_missing", f"Recording file missing: {r.path}")
    return serve_wav(path, request)


@router.get("/api/audio/prompts/{name}")
async def prompt_audio(name: str, request: Request) -> Response:
    rt = runtime(request)
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.wav", name):
        raise ApiError(404, "not_found", "No such prompt")
    path = rt.config.prompts_dir / name
    if not path.exists():
        raise ApiError(404, "not_found", "No such prompt")
    return serve_wav(path, request)


def serve_wav(path: Path, request: Request) -> Response:
    """WAV with HTTP Range support so the browser's <audio> can seek."""
    size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes"}
    rng = request.headers.get("range")
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng or "")
    if not m:
        return FileResponse(path, media_type="audio/wav", headers=headers)
    start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2) or 0))
    end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
    end = min(end, size - 1)
    if start > end or start >= size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    length = end - start + 1

    def chunks():
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(64 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers.update({"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(length)})
    return StreamingResponse(chunks(), status_code=206, media_type="audio/wav", headers=headers)
