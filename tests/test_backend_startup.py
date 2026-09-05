import os
import subprocess
from pathlib import Path

from backend import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_importing_backend_does_not_create_runtime_session_file(tmp_path):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT)

    subprocess.run(
        [str(PROJECT_ROOT / ".venv/bin/python"), "-c", "import backend.main"],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert not (tmp_path / ":memory:.ses").exists()


def test_prepare_database_creates_tables_before_running_migrations(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "create_tables", lambda: calls.append("create"))
    monkeypatch.setattr(main, "run_migrations", lambda: calls.append("migrate"))

    main.prepare_database()

    assert calls == ["create", "migrate"]
