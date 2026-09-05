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
