import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import app
from backend.db import create_tables
from backend.db.migrations.runner import run_background_migrations, run_migrations

logger = logging.getLogger(__name__)


def prepare_database() -> None:
    create_tables()
    run_migrations()


def _run_background_maintenance() -> None:
    try:
        run_background_migrations()
    except Exception:
        # Maintenance (e.g. collation reindex) must never take the app down; it
        # retries on the next startup. Failing here would only crash a worker.
        logger.exception("Background database maintenance failed")


@asynccontextmanager
async def lifespan(_app):
    prepare_database()
    # Slow maintenance runs off-thread so the healthcheck endpoint is reachable
    # immediately instead of waiting for a full-database reindex to finish.
    threading.Thread(
        target=_run_background_maintenance, name="db-maintenance", daemon=True
    ).start()
    yield


app.router.lifespan_context = lifespan


def frontend_origins() -> list[str]:
    configured = os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Serve the built frontend (Vite output) when present. The API router is
# registered first, so /api/v1/* still takes precedence over this catch-all
# mount. html=True makes StaticFiles fall back to index.html for SPA routes.
# The mount is skipped in API-only environments where dist/ hasn't been built.
_FRONTEND_DIST = Path(
    os.environ.get(
        "FRONTEND_DIST",
        Path(__file__).resolve().parent.parent / "frontend" / "dist",
    )
)
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
