import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dev_command_limits_reload_watching_to_application_source():
    result = subprocess.run(
        ["make", "--dry-run", "dev"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--reload-dir backend" in result.stdout
