import importlib
from types import SimpleNamespace

from backend.db.migrations import runner


def test_run_migrations_applies_numbered_modules_in_order(monkeypatch):
    discovered = [
        SimpleNamespace(name="0002_second"),
        SimpleNamespace(name="0003_third"),
        SimpleNamespace(name="helpers"),
        SimpleNamespace(name="0001_first"),
    ]
    applied = []

    monkeypatch.setattr(runner.pkgutil, "iter_modules", lambda path: discovered)
    monkeypatch.setattr(
        runner.importlib,
        "import_module",
        lambda name: SimpleNamespace(upgrade=lambda: applied.append(name)),
    )

    runner.run_migrations()

    assert applied == [
        "backend.db.migrations.0001_first",
        "backend.db.migrations.0002_second",
        "backend.db.migrations.0003_third",
    ]


def test_background_migrations_are_split_from_blocking_ones(monkeypatch):
    discovered = [
        SimpleNamespace(name="0001_first"),
        SimpleNamespace(name="0002_heavy"),
    ]
    modules = {
        "backend.db.migrations.0001_first": SimpleNamespace(
            upgrade=lambda: applied.append("0001_first")
        ),
        "backend.db.migrations.0002_heavy": SimpleNamespace(
            BACKGROUND=True, upgrade=lambda: applied.append("0002_heavy")
        ),
    }
    applied = []

    monkeypatch.setattr(runner.pkgutil, "iter_modules", lambda path: discovered)
    monkeypatch.setattr(runner.importlib, "import_module", lambda name: modules[name])

    runner.run_migrations()
    assert applied == ["0001_first"]

    runner.run_background_migrations()
    assert applied == ["0001_first", "0002_heavy"]


def test_collation_migration_is_marked_background():
    migration = importlib.import_module(
        "backend.db.migrations.0005_refresh_database_collation"
    )
    assert getattr(migration, "BACKGROUND", False) is True


def test_internal_document_migration_is_safe_to_rerun():
    migration = importlib.import_module(
        "backend.db.migrations.0003_add_internal_documents_and_suggestions"
    )

    assert all(
        sql.strip().upper() != "DELETE FROM INTERNAL_DOCUMENT_CHUNKS"
        for sql in migration.STATEMENTS
    )
