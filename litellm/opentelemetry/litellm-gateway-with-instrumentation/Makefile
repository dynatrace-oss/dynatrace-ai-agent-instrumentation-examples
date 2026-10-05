SHELL := /bin/bash
-include ../.env

export PORT ?= 8000
export COLLECTOR_BASE_URL ?= http://localhost:4318
export DT_ENDPOINT ?= https://your-tenant.live.dynatrace.com
export DT_API_TOKEN ?= dt0c01.YOUR_TOKEN_HERE

.PHONY: install run request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies for fastapi-instrumentation
	@echo "Installing Python dependencies for fastapi-instrumentation..."
	@if [ -f requirements.txt ]; then \
	  if command -v uv >/dev/null 2>&1; then \
	    uv sync || python3 -m pip install -r requirements.txt; \
	  else \
	    python3 -m pip install -r requirements.txt; \
	  fi \
	else \
	  echo "No requirements.txt found — skipping install."; \
	fi

run: ## Start the FastAPI demo on $(PORT)
	@echo "Starting FastAPI demo on port $(PORT) (Collector should be running separately)"
	COLLECTOR_BASE_URL=$(COLLECTOR_BASE_URL) uv run python3 -m uvicorn main:app --host 0.0.0.0 --port $(PORT)

request: ## POST /generate to localhost:$(PORT)
	@curl -s -X POST http://localhost:$(PORT)/generate \
	  -H 'Content-Type: application/json' \
	  -d '{"prompt":"Write a haiku about the ocean"}' | python3 -m json.tool

stop: ## (Manual) stop the process started by run (use pkill as fallback)
	@echo "Stopping uvicorn processes listening on $(PORT)..."
	@pkill -f "uvicorn.*:$(PORT)" || true

logs: ## Tail local stdout/stderr if you directed it; placeholder
	@echo "Collector/app logs should be available in your terminal or log files."