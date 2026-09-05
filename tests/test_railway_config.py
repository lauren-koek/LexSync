import json
import os
import shlex
import subprocess
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_railway_start_command_expands_the_injected_port(tmp_path):
    config = tomllib.loads((PROJECT_ROOT / "railway.toml").read_text())
    fake_uvicorn = tmp_path / "uvicorn"
    fake_uvicorn.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    fake_uvicorn.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PORT": "4321",
    }

    result = subprocess.run(
        shlex.split(config["deploy"]["startCommand"]),
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines()[-2:] == ["--port", "4321"]


def test_docker_start_command_expands_the_injected_port(tmp_path):
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    command = json.loads(
        next(line.removeprefix("CMD ") for line in dockerfile.splitlines() if line.startswith("CMD "))
    )
    fake_uvicorn = tmp_path / "uvicorn"
    fake_uvicorn.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    fake_uvicorn.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PORT": "4321",
    }

    result = subprocess.run(
        command,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines()[-2:] == ["--port", "4321"]
