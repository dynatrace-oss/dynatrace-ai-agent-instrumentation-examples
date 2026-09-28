SHELL := /bin/bash

UV ?= uv
PYTHON ?= 3.12
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: help setup test emit clean

help:
	@printf '%s\n' \
	  'make real-test          Run the real Cursor headless CLI in Kubernetes' \
	  'make cursor-k8s-logs    Show the latest real Cursor Job output' \
	  'make cursor-k8s-status  Show Job and Pod status' \
	  'make cursor-k8s-clean   Delete the real Cursor test namespace' \
	  'make test               Validate the dashboard files locally' \
	  'make emit               Synthetic OTLP connectivity test only'

setup:
	$(UV) venv --python $(PYTHON) $(VENV)
	$(UV) pip install --python $(VENV_PYTHON) -r requirements.txt

test: setup
	$(UV) run --no-project --python $(VENV_PYTHON) python -m unittest -v test_dashboard.py

# This remains available only for isolated OTLP connectivity testing. It is not Cursor.
emit: setup
	$(UV) run --no-project --python $(VENV_PYTHON) python test_connection.py

clean:
	rm -rf $(VENV) __pycache__
