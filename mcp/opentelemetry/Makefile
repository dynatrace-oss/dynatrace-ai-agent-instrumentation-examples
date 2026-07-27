SHELL            := /bin/bash
-include .env
export

APP_IMAGE        ?=
BUILD_PLATFORM   ?= linux/amd64
PORT             ?= 8000

.PHONY: install run build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies for agent and MCP server
	cd ai-agent && uv sync
	cd mpc-server && npm install

run: ## Run app locally on port $(PORT)
	(cd mpc-server && PORT=3000 npm run start) & \
	cd ai-agent && uv run python3 -m uvicorn server:app --host 0.0.0.0 --port $(PORT)

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /invoke to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/invoke \
	  -H 'Content-Type: application/json' \
	  -d '{"message":"What is the weather in New York?"}' | python3 -m json.tool
