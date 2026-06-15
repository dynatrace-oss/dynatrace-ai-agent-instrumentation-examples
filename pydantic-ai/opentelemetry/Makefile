SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000
PYTHON           := $(shell [ -f .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: install run build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	$(PYTHON) -m pip install -r backend/requirements.txt

run: ## Run the Pydantic AI backend on port $(PORT)
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port $(PORT)

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /chat to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/chat \
	  -H 'Content-Type: application/json' \
	  -d '{"message":"Write a haiku about the ocean"}' | python3 -m json.tool
