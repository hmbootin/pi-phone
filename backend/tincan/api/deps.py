"""Shared FastAPI plumbing: runtime access, auth, the error envelope."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from tincan.runtime import Runtime

COOKIE = "tincan_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30
PUBLIC_PATHS = {"/api/auth/login", "/healthz"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def serializer(request: Request) -> URLSafeTimedSerializer:
    return request.app.state.serializer


def make_session_cookie(s: URLSafeTimedSerializer) -> str:
    return s.dumps({"role": "parent"})


def session_valid(s: URLSafeTimedSerializer, value: str | None) -> bool:
    if not value:
        return False
    try:
        data: Any = s.loads(value, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return False
    return isinstance(data, dict) and data.get("role") == "parent"
