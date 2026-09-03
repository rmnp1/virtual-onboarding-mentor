import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.auth.routes import router as auth_router
from app.chat.routes import router as chat_router
from app.config import Settings, settings
from app.feedback.routes import router as feedback_router
from app.metrics.routes import router as metrics_router
from app.models.base import init_db
from app.personalization.routes import router as personalization_router
from app.scenarios.routes import router as scenarios_router

logger = logging.getLogger(__name__)


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def _configure_logging(cfg: Settings) -> None:
    level = logging.INFO if cfg.log_level == "INFO" else logging.DEBUG
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root.handlers = [handler]
    for name in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).propagate = False


def build_app(cfg: Settings) -> FastAPI:
    _configure_logging(cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db()
        yield

    app = FastAPI(
        title="Virtual Onboarding Mentor",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if cfg.expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if cfg.expose_docs else None,
    )

    app.add_middleware(_SecurityHeadersMiddleware)

    _cors_origins = [origin.strip() for origin in cfg.cors_origins.split(",") if origin.strip()]
    if _cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(scenarios_router)
    app.include_router(personalization_router)
    app.include_router(feedback_router)
    app.include_router(metrics_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

    return app


app = build_app(settings)
