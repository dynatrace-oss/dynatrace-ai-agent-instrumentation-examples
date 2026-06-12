SHELL            := /bin/bash
-include .env
export

.PHONY: install run build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run the Strands agent demo
	uv run python3 main.py

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## Not applicable — this demo runs as a CLI, not an HTTP server
	@echo "request: this demo runs as a CLI script, not an HTTP server; use 'make run' instead"
