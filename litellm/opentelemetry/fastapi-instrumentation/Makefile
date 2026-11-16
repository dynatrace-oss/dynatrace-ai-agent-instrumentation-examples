SHELL := /bin/bash
-include ../.env
export

PORT                 ?= 8000
COLLECTOR_BASE_URL   ?= localhost:4317
DT_ENDPOINT          ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN         ?= dt0c01.*****
COLLECTOR_CONTAINER  ?= otel-collector-litellm-fastapi

include ../collector.mk

.PHONY: install run request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies (uses ../pyproject.toml)
	uv sync

run: ## Start collector + FastAPI demo (main.py) on port $(PORT)
	@$(MAKE) _collector CONFIG=../otel-collector-config.yaml
	uv run python3 -m uvicorn main:app --host 0.0.0.0 --port $(PORT)

request: ## POST /chat/completions to localhost:$(PORT)
	@curl -s -X POST http://localhost:$(PORT)/chat/completions \
	  -H 'Content-Type: application/json' \
	  -d '{"model":"gpt-5.4-mini","messages":[{"role":"user","content":"Write a haiku about observability"}]}' | python3 -m json.tool

stop: ## Stop the demo and the collector container
	-@pkill -f "uvicorn main:app" || true
	@$(MAKE) _collector-stop

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log
