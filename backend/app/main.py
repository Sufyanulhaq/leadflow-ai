"""Application factory. Run with:  uvicorn app.main:create_app --factory"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .assistant import Assistant
from .config import Settings, load_settings
from .db import init_db, make_engine
from .notify import Transport, http_post
from .routes import admin, public
from .security import RateLimiter
from .seed import seed_demo

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
FRONTEND_DIST = APP_DIR.parents[1] / "frontend" / "dist"


def create_app(
    settings: Settings | None = None,
    *,
    anthropic_client: object | None = None,
    transport: Transport = http_post,
    sleep: Callable[[float], None] = time.sleep,
) -> FastAPI:
    """The keyword arguments exist so tests can swap in a fake Claude client, webhook and clock."""
    settings = settings or load_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)

    app = FastAPI(title="LeadFlow AI", version="0.1.0", description="An AI front desk for dental and physiotherapy clinics.")
    app.state.settings = settings
    app.state.engine = engine
    app.state.assistant = Assistant(settings, anthropic_client)
    app.state.limiter = RateLimiter()
    app.state.transport = transport
    app.state.sleep = sleep

    if settings.seed_demo:
        with Session(engine) as session:
            seed_demo(session)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )

    @app.exception_handler(RequestValidationError)
    async def friendly_validation_errors(_: Request, exc: RequestValidationError):
        """One readable sentence instead of pydantic's list, so the widget can show it as it is."""
        messages = []
        for error in exc.errors():
            text = str(error["msg"]).removeprefix("Value error, ")
            if error["type"] != "value_error":
                text = f"{error['loc'][-1]}: {text}"
            messages.append(text if text.endswith(".") else text + ".")
        return JSONResponse({"detail": " ".join(messages)}, status_code=422)

    app.include_router(public.router)
    app.include_router(admin.router)

    @app.get("/widget.js", include_in_schema=False)
    def widget():
        return FileResponse(
            STATIC_DIR / "widget.js", media_type="application/javascript", headers={"Cache-Control": "public, max-age=300"}
        )

    @app.get("/demo", include_in_schema=False)
    def demo():
        return FileResponse(STATIC_DIR / "demo.html")

    if FRONTEND_DIST.is_dir():
        app.mount("/admin", StaticFiles(directory=FRONTEND_DIST, html=True), name="admin")

    return app
