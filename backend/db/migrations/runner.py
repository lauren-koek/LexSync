"""Discover and apply idempotent database migrations in filename order."""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re

from backend.db import migrations

logger = logging.getLogger(__name__)

_MIGRATION_MODULE = re.compile(r"^\d{4}_[a-z0-9_]+$")


def _apply(*, background: bool) -> None:
    names = sorted(
        module.name
        for module in pkgutil.iter_modules(migrations.__path__)
        if _MIGRATION_MODULE.fullmatch(module.name)
    )
    for name in names:
        module_name = f"{migrations.__name__}.{name}"
        module = importlib.import_module(module_name)
        # Background migrations (e.g. a full-database REINDEX) can take longer
        # than the platform healthcheck window, so they must not run on the
        # request-serving startup path. They are applied separately, off-thread.
        if bool(getattr(module, "BACKGROUND", False)) != background:
            continue
        logger.info("Applying database migration: %s", name)
        module.upgrade()


def run_migrations() -> None:
    """Apply fast, blocking migrations required before the app serves traffic."""
    _apply(background=False)


def run_background_migrations() -> None:
    """Apply slow maintenance migrations that must not block startup/healthcheck."""
    _apply(background=True)
