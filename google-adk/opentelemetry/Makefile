SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

.PHONY: install run build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run the Google ADK agent (web UI on port $(PORT))
	uv run adk web --port $(PORT)

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## Not applicable — this demo uses ADK web UI; open http://localhost:$(PORT) in a browser
	@echo "request: open http://localhost:$(PORT) in a browser to interact with the agent"
