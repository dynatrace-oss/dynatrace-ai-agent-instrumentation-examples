SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

.PHONY: install run build push request build-fixtures test help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run app locally on port $(PORT)
	uv run python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

build-fixtures: ## Regenerate fixtures.json from the source datasets (dev only)
	uv run python3 build_fixtures.py

test: ## Run the test suite
	uv run pytest -q

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /ingest to localhost:$(PORT) — ship all fixture spans
	curl -s -X POST http://localhost:$(PORT)/ingest
