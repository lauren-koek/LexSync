"""Discover and apply idempotent database migrations in filename order."""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re

from backend.db import migrations

logger = logging.getLogger(__name__)

_MIGRATION_MODULE = re.compile(r"^\d{4}_[a-z0-9_]+$")


def run_migrations() -> None:
    names = sorted(
        module.name
        for module in pkgutil.iter_modules(migrations.__path__)
        if _MIGRATION_MODULE.fullmatch(module.name)
    )
    for name in names:
        module_name = f"{migrations.__name__}.{name}"
        logger.info("Applying database migration: %s", name)
        module = importlib.import_module(module_name)
        module.upgrade()
