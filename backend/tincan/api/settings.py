from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import ValidationError

from tincan import store
from tincan.api.deps import ApiError, runtime
from tincan.schemas import Settings
from tincan.sounds import BUILTIN_RINGTONES, ringtone_exists

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings(request: Request) -> Settings:
    return runtime(request).settings()


@router.patch("")
async def patch_settings(body: dict[str, Any], request: Request) -> Settings:
    rt = runtime(request)
    current = rt.settings().model_dump()
    for k, v in body.items():
        if k not in Settings.model_fields:
            raise ApiError(400, "unknown_setting", f"Unknown setting {k!r}")
        current[k] = v
    try:
        merged = Settings.model_validate(current)
    except ValidationError as exc:
        raise ApiError(400, "invalid_settings", str(exc.errors()[0].get("msg", "invalid"))) from exc
    if "ringtone" in body and not ringtone_exists(merged.ringtone, rt.config.data_dir):
        raise ApiError(
            422,
            "unknown_ringtone",
            f"No ringtone named {merged.ringtone!r}; pick one of "
            f"{', '.join(BUILTIN_RINGTONES)} or upload one at POST /api/ringtones",
        )
    store.save_settings(rt.db, merged)
    return merged
