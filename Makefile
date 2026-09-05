.PHONY: dev install test clean

PYTHON ?= python3.14
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
PYTEST := $(VENV)/bin/pytest

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)

$(VENV)/.installed: requirements.txt requirements-dev.txt $(VENV_PYTHON)
	$(VENV_PIP) install -r requirements-dev.txt
	@touch $(VENV)/.installed

install: $(VENV)/.installed

dev: install
	$(UVICORN) backend.main:app --reload --reload-dir backend --host 0.0.0.0 --port 8000

test: install
	$(VENV_PYTHON) -m pytest -q

clean:
	rm -rf $(VENV)
