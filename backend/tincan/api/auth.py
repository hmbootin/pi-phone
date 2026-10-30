from __future__ import annotations

import secrets

from fastapi import APIRouter, Request, Response

from tincan.api.deps import (
    COOKIE,
    SESSION_MAX_AGE,
    ApiError,
    make_session_cookie,
    runtime,
    serializer,
)
from tincan.schemas import LoginIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response) -> dict:
    rt = runtime(request)
    if not secrets.compare_digest(body.password, rt.config.tincan_parent_password):
        raise ApiError(401, "bad_password", "Wrong password")
    response.set_cookie(
        COOKIE,
        make_session_cookie(serializer(request)),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return {"ok": True}


@router.post("/logout", status_code=204)
async def logout(response: Response) -> Response:
    response.delete_cookie(COOKIE)
    response.status_code = 204
    return response


@router.get("/me")
async def me() -> dict:
    return {"role": "parent"}
