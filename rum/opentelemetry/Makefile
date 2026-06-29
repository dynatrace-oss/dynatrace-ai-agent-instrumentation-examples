SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

.PHONY: install run build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies for backend
	uv sync

run: ## Run the backend on port $(PORT)
	cd backend && uv run python3 -m uvicorn main:app --host 0.0.0.0 --port $(PORT)

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## GET /health from localhost:$(PORT)
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool
