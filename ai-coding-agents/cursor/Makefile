# cursor-Makefile
# Single Makefile that supports:
#  - local Python test + preflight
#  - Kubernetes real-test (existing flow)
#  - Docker real-test (self-contained image that runs the real Cursor workload)
#
# Usage examples:
#   make preflight                 # Validate CURSOR_API_KEY (local)
#   make docker-build-real         # Build the self-contained real-test image
#   make docker-run-real           # Run the real test in Docker (foreground)
#   make docker-run-real-detached  # Run the real test in Docker (detached)
#   make docker-logs               # Tail detached run logs
#   make compose-up-real           # Build + docker compose up (convenience)
#   make compose-down-real
#   make real-test                 # Alias -> docker-run-real (no k8s)
#   make cursor-k8s-run            # Existing k8s path (unchanged)

SHELL := /bin/bash

# Python / venv helpers (existing)
UV ?= uv
PYTHON ?= 3.12
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

# kubectl / k8s vars (existing)
KUBECTL := $(if $(strip $(KUBECTL)),$(strip $(KUBECTL)),kubectl)
CURSOR_NAMESPACE ?= cursor-otel-test
CURSOR_JOB ?= cursor-real-test
CURSOR_MANIFEST ?= k8s/cursor-real-test.yaml
CURSOR_TIMEOUT ?= 15m

# Docker vars (new)
DOCKER ?= docker
DOCKER_IMAGE_REAL ?= cursor-real-test:latest
DOCKERFILE_REAL ?= docker/Dockerfile
COMPOSE ?= docker compose
COMPOSE_FILE ?= docker/docker-compose.yml
DETACHED_CONTAINER_NAME ?= cursor-real-run

# Common env file (must contain CURSOR_API_KEY)
ENV_FILE ?= .env

.PHONY: help setup test emit preflight \
        docker-build-real docker-run-real docker-run-real-detached docker-logs compose-up-real compose-down-real \
        real-test \
        cursor-k8s-check cursor-k8s-secret cursor-k8s-run cursor-k8s-logs cursor-k8s-status cursor-k8s-clean \
        clean

# -----------------------
# Help
# -----------------------
help:
	@printf '%s\n' \
	  'make preflight                 # Run local preflight checks (cursor key + optional DT endpoints)' \
	  'make docker-build-real        # Build self-contained Cursor real-test image' \
	  'make docker-run-real          # Run real Cursor workload in Docker (foreground)' \
	  'make docker-run-real-detached # Run real Cursor workload in Docker (detached)' \
	  'make docker-logs              # Tail logs from detached run' \
	  'make compose-up-real          # Compose up (build + run) — convenience' \
	  'make compose-down-real        # Compose down' \
	  'make real-test                # Alias -> docker-run-real (no k8s)' \
	  'make cursor-k8s-run           # Run real test in Kubernetes (existing flow)' \
	  'make test                    # Run dashboard contract tests locally' \
	  'make emit                    # Run synthetic OTLP emitter (diagnostic only)'

# -----------------------
# Python / local tests (existing)
# -----------------------
setup:
	$(UV) venv --python $(PYTHON) $(VENV)
	$(UV) pip install --python $(VENV_PYTHON) -r cursor-requirements.txt

test: setup
	$(UV) run --no-project --python $(VENV_PYTHON) python -m unittest -v cursor-test_dashboard.py

# Diagnostic emitter (not the real Cursor workload)
emit: setup
	$(UV) run --no-project --python $(VENV_PYTHON) python cursor-test_connection.py

# Local preflight: validate .env and run the repo preflight check (cursor-test_connection.py --preflight)
preflight:
	@test -f $(ENV_FILE) || { echo "ERROR: $(ENV_FILE) not found. cp cursor-env.example .env and set CURSOR_API_KEY"; exit 1; }
	@grep -Eq '^[[:space:]]*CURSOR_API_KEY=.+' $(ENV_FILE) || { echo 'ERROR: CURSOR_API_KEY is missing from $(ENV_FILE)'; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo 'python3 not found in PATH'; exit 1; }
	@echo "Running local preflight (validates Cursor key and optional DT endpoints)..."
	@python3 cursor-test_connection.py --preflight || { echo "Preflight failed; fix env/keys and re-run"; exit 1; }

# -----------------------
# Docker-first real test (new)
# -----------------------
# Build a self-contained image that bakes in the Cursor CLI and seed repo.
docker-build-real:
	@command -v $(DOCKER) >/dev/null 2>&1 || { echo "docker not found in PATH"; exit 1; }
	@echo "Building real-test image ($(DOCKER_IMAGE_REAL)) from $(DOCKERFILE_REAL)"
	@$(DOCKER) build -f $(DOCKERFILE_REAL) -t $(DOCKER_IMAGE_REAL) .

# Run the real test in Docker (foreground). Image should have start script that expects CURSOR_API_KEY in env.
docker-run-real: docker-build-real
	@test -f $(ENV_FILE) || { echo "ERROR: $(ENV_FILE) not found. cp cursor-env.example .env and set CURSOR_API_KEY"; exit 1; }
	@echo "Running real Cursor workload in Docker (foreground). Provide CURSOR_API_KEY in $(ENV_FILE)."
	@$(DOCKER) run --env-file $(ENV_FILE) --rm $(DOCKER_IMAGE_REAL)

# Detached run (keeps container for logs)
docker-run-real-detached: docker-build-real
	@test -f $(ENV_FILE) || { echo "ERROR: $(ENV_FILE) not found. cp cursor-env.example .env and set CURSOR_API_KEY"; exit 1; }
	@echo "Running real Cursor workload in Docker (detached). Container name: $(DETACHED_CONTAINER_NAME)"
	@$(DOCKER) run --env-file $(ENV_FILE) --name $(DETACHED_CONTAINER_NAME) -d $(DOCKER_IMAGE_REAL) || true

# Tail logs from detached run
docker-logs:
	@command -v $(DOCKER) >/dev/null 2>&1 || { echo "docker not found in PATH"; exit 1; }
	@$(DOCKER) logs -f $(DETACHED_CONTAINER_NAME) || { echo "No logs for container '$(DETACHED_CONTAINER_NAME)'"; exit 1; }

# Convenience compose flow: build the image then run compose up
compose-up-real:
	@command -v $(COMPOSE) >/dev/null 2>&1 || { echo "docker compose not found in PATH"; exit 1; }
	@$(MAKE) docker-build-real
	@$(COMPOSE) -f $(COMPOSE_FILE) up --build

compose-down-real:
	@command -v $(COMPOSE) >/dev/null 2>&1 || { echo "docker compose not found in PATH"; exit 1; }
	@$(COMPOSE) -f $(COMPOSE_FILE) down

# Default real-test maps to Docker flow (no Kubernetes)
real-test: docker-run-real

# -----------------------
# Clean
# -----------------------
clean:
	@rm -rf $(VENV) __pycache__ || true