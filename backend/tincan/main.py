"""FastAPI app factory. `tincan serve` runs it; tests build it with their own Config."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer

from tincan.api import auth, calls, contacts, dev, features, recordings, settings, system
from tincan.api.deps import COOKIE, PUBLIC_PATHS, ApiError, error_response, session_valid
from tincan.config import Config
from tincan.runtime import Runtime

log = logging.getLogger(__name__)


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()
    config.warn_insecure()
    rt = Runtime(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await rt.start()
        try:
            yield
        finally:
            await rt.stop()

    app = FastAPI(
        title="Tin Can", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
    )
    app.state.runtime = rt
    app.state.serializer = URLSafeTimedSerializer(config.secret_key(), salt="tincan-session")

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = {401: "unauthorized", 404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "error"
        )
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        return error_response(
            422, "validation_error", f"{loc}: {first.get('msg', 'invalid')}".strip(": ")
        )

    @app.middleware("http")
    async def _auth(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in PUBLIC_PATHS:
            if not session_valid(app.state.serializer, request.cookies.get(COOKIE)):
                return error_response(401, "unauthorized", "Log in first")
        return await call_next(request)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    for r in (auth, contacts, features, settings, calls, recordings, system):
        app.include_router(r.router)
    if config.tincan_fake_ari:
        app.include_router(dev.router)

    ui_dir = config.tincan_ui_dir
    if ui_dir and Path(ui_dir).is_dir():
        mount_ui(app, Path(ui_dir))
    else:
        log.info("no UI dir (TINCAN_UI_DIR=%s); API only", ui_dir)
    return app


def mount_ui(app: FastAPI, ui_dir: Path) -> None:
    """Serve the built parent app with SPA fallback to index.html."""
    assets = ui_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    index = ui_dir / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (ui_dir / path).resolve()
        if path and candidate.is_file() and ui_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


def factory() -> FastAPI:
    return create_app()
