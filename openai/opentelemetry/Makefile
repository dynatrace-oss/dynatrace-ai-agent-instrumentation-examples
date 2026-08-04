SHELL               := /bin/bash

# ---------------------------------------------------------------------------
# Configuration — set in .env (KEY=value format, no export, no quotes)
# ---------------------------------------------------------------------------
-include .env
export

DT_ENDPOINT         ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN        ?= dt0c01.*****

.PHONY: run request install help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run the app, exporting traces and metrics directly to Dynatrace
	@uv run python3 app.py

request: ## Send a haiku request to Dynatrace
	@uv run python3 app.py
