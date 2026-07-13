SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

.PHONY: install run stop build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies for backend
	uv sync

run: ## Run the backend on port $(PORT)
	cd backend && uv run python3 -m uvicorn main:app --host 0.0.0.0 --port $(PORT)

stop: ## Stop the backend (no-op; process is managed by the test runner)
	@true

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /api/ask to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/api/ask \
	  -H 'Content-Type: application/json' \
	  -d '{"question":"Who invented jazz?","conversation_id":"$(shell python3 -c \"import uuid; print(uuid.uuid4())\")"}' | python3 -m json.tool
