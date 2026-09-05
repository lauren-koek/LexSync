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


def _startup_database() -> None:
    # Runs off the request-serving path. Schema prep (create_tables + fast
    # migrations) can block on locks held by a still-running previous deploy —
    # during a rolling deploy the old container keeps serving until the new one
    # is healthy, so a DDL statement here waits indefinitely and the healthcheck
    # never passes, deadlocking the swap. Keeping it off-thread lets uvicorn
    # answer /health immediately; once Railway swaps in this deploy the old one
    # stops, the locks clear, and preparation completes.
    try:
        prepare_database()
    except Exception:
        logger.exception("Database preparation failed")
    try:
        run_background_migrations()
    except Exception:
        # Maintenance (e.g. collation reindex) must never take the app down; it
        # retries on the next startup. Failing here would only crash a worker.
        logger.exception("Background database maintenance failed")


@asynccontextmanager
async def lifespan(_app):
    # Do not block startup on the database: the healthcheck endpoint needs no DB,
    # and blocking here is what kept new deploys from ever going healthy.
    threading.Thread(
        target=_startup_database, name="db-startup", daemon=True
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
