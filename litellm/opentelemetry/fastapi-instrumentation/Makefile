SHELL := /bin/bash
-include ../.env

export PORT ?= 4000
export COLLECTOR_BASE_URL ?= http://localhost:4318
export DT_ENDPOINT ?= https://your-tenant.live.dynatrace.com
export DT_API_TOKEN ?= dt0c01.YOUR_TOKEN_HERE
export LITELLM_MASTER_KEY ?= sk-admin-local

.PHONY: install run request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies for the gateway demo
	@echo "Installing Python dependencies for litellm gateway..."
	@if [ -f requirements.txt ]; then \
	  if command -v uv >/dev/null 2>&1; then \
	    uv sync || python3 -m pip install -r requirements.txt; \
	  else \
	    python3 -m pip install -r requirements.txt; \
	  fi \
	else \
	  echo "No requirements.txt found — skipping install."; \
	fi

run: ## Start the LiteLLM proxy gateway (basic.py)
	@echo "Starting LiteLLM gateway (basic.py) on port $(PORT). Collector should be running separately."
	@# ensure envs available to the process
	COLLECTOR_BASE_URL=$(COLLECTOR_BASE_URL) LITELLM_MASTER_KEY=$(LITELLM_MASTER_KEY) uv run python3 basic.py

request: ## POST /chat/completions to gateway on localhost:$(PORT)
	@curl -s -X POST http://localhost:$(PORT)/chat/completions \
	  -H 'Content-Type: application/json' \
	  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
	  -d '{ "model":"ollama-llama3.2", "messages": [{"role":"user","content":"Write a haiku about observability"}], "temperature":0.3, "max_tokens":50 }' | python3 -m json.tool

stop: ## (Manual) stop the process started by run (use pkill as fallback)
	@echo "Stopping gateway python processes..."
	@pkill -f "basic.py" || true

logs: ## Tail local stdout/stderr if you directed it; placeholder
	@echo "Gateway logs should be available in your terminal or log files."