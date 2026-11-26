"""Ringtones: the built-in ones plus parent uploads under <data_dir>/ringtones (docs/api.md)."""

from __future__ import annotations

import io
import re
import wave
from pathlib import Path

from fastapi import APIRouter, Request, Response, UploadFile

from tincan import store
from tincan.api.deps import ApiError, runtime
from tincan.api.recordings import serve_wav
from tincan.schemas import RingtoneOut
from tincan.sounds import (
    BUILTIN_RINGTONES,
    DEFAULT_RINGTONE,
    RINGTONE_NAME,
    RINGTONE_RATE,
    ringtones_dir,
    uploaded_ringtone_path,
)
from tincan.tts.piper import convert_wav

router = APIRouter(prefix="/api/ringtones", tags=["ringtones"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_SECONDS = 10.0


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return round(w.getnframes() / w.getframerate(), 2)


def _entry(name: str, path: Path, builtin: bool) -> RingtoneOut:
    return RingtoneOut(
        name=name,
        builtin=builtin,
        duration_seconds=_duration(path),
        audio_url=f"/api/ringtones/{name}/audio",
    )


def _uploads(data_dir: Path) -> list[tuple[str, Path]]:
    d = ringtones_dir(data_dir)
    if not d.is_dir():
        return []
    found = []
    for p in sorted(d.glob("*.wav")):
        if RINGTONE_NAME.fullmatch(p.stem) and p.stem not in BUILTIN_RINGTONES:
            found.append((p.stem, p))
    return found


def slug(filename: str) -> str:
    stem = Path(filename or "").stem.lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", stem).strip("-_")
    return s[:32].rstrip("-_")


@router.get("")
async def list_ringtones(request: Request) -> list[RingtoneOut]:
    rt = runtime(request)
    out = [_entry(n, p, True) for n, p in BUILTIN_RINGTONES.items()]
    out += [_entry(n, p, False) for n, p in _uploads(rt.config.data_dir)]
    return out


@router.post("", status_code=201)
async def upload_ringtone(file: UploadFile, request: Request) -> RingtoneOut:
    rt = runtime(request)
    name = slug(file.filename or "")
    if not name:
        raise ApiError(400, "bad_name", "The file name must contain a letter or digit")
    if name in BUILTIN_RINGTONES:
        raise ApiError(409, "ringtone_builtin", f"{name!r} is a built-in ringtone; rename the file")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "too_large", f"Ringtones must be under {MAX_UPLOAD_BYTES // 1024} KB")
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            width, rate, frames = w.getsampwidth(), w.getframerate(), w.getnframes()
    except (wave.Error, EOFError) as exc:
        raise ApiError(400, "invalid_wav", "Only WAV files (16-bit PCM) are accepted") from exc
    if width != 2:
        raise ApiError(400, "invalid_wav", f"Expected 16-bit PCM WAV, got {width * 8}-bit")
    seconds = frames / rate if rate else 0.0
    if seconds > MAX_UPLOAD_SECONDS:
        limit = f"{MAX_UPLOAD_SECONDS:.0f} s"
        msg = f"Ringtones must be {limit} or shorter (this one is {seconds:.1f} s)"
        raise ApiError(422, "too_long", msg)
    if frames == 0:
        raise ApiError(400, "invalid_wav", "The WAV file is empty")

    d = ringtones_dir(rt.config.data_dir)
    d.mkdir(parents=True, exist_ok=True)
    raw = d / f".{name}.upload.wav"
    tmp = d / f".{name}.tmp.wav"
    final = d / f"{name}.wav"
    try:
        raw.write_bytes(data)
        convert_wav(raw, tmp, RINGTONE_RATE)  # mono, 16 kHz, like the built-ins
        tmp.replace(final)
    finally:
        raw.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
    return _entry(name, final, False)


@router.delete("/{name}", status_code=204)
async def delete_ringtone(name: str, request: Request) -> Response:
    rt = runtime(request)
    if name in BUILTIN_RINGTONES:
        raise ApiError(409, "ringtone_builtin", "Built-in ringtones cannot be deleted")
    path = uploaded_ringtone_path(name, rt.config.data_dir)
    if path is None:
        raise ApiError(404, "not_found", f"No ringtone named {name!r}")
    path.unlink()
    settings = rt.settings()
    if settings.ringtone == name:
        store.save_settings(rt.db, settings.model_copy(update={"ringtone": DEFAULT_RINGTONE}))
    return Response(status_code=204)


@router.get("/{name}/audio")
async def ringtone_audio(name: str, request: Request) -> Response:
    rt = runtime(request)
    path = BUILTIN_RINGTONES.get(name) or uploaded_ringtone_path(name, rt.config.data_dir)
    if path is None or not path.is_file():
        raise ApiError(404, "not_found", f"No ringtone named {name!r}")
    return serve_wav(path, request)
