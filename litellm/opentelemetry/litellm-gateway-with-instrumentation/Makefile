SHELL := /bin/bash
-include .env
export

PORT                 ?= 8000
COLLECTOR_BASE_URL   ?= http://localhost:4318
DT_ENDPOINT          ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN         ?= dt0c01.*****
LITELLM_MASTER_KEY   ?= sk-admin-local
COLLECTOR_CONTAINER  ?= otel-collector-litellm-gateway

include ../collector.mk

.PHONY: install run request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Start collector + LiteLLM proxy gateway (basic.py) on port $(PORT)
	@$(MAKE) _collector CONFIG=../otel-collector-config.yaml
	uv run python3 basic.py

request: ## POST /chat/completions to the gateway on localhost:$(PORT)
	@curl -s -X POST http://localhost:$(PORT)/chat/completions \
	  -H 'Content-Type: application/json' \
	  -H "Authorization: Bearer $(LITELLM_MASTER_KEY)" \
	  -d '{"model":"ollama-llama3.2","messages":[{"role":"user","content":"Write a haiku about observability"}],"max_tokens":50}' | python3 -m json.tool

stop: ## Stop the gateway and the collector container
	-@pkill -f "python3 basic.py" || true
	@$(MAKE) _collector-stop

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log
