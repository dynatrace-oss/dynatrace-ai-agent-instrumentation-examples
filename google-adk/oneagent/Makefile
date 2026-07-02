SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

.PHONY: install run request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run app locally on port $(PORT)
	uv run python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

request: ## POST /research to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/research \
	  -H 'Content-Type: application/json' \
	  -d '{"topic":"Attention is All You Need"}'
