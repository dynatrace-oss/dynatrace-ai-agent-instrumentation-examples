SHELL            := /bin/bash
-include .env
export

APP_IMAGE        ?=
BUILD_PLATFORM   ?= linux/amd64
PORT             ?= 8000

.PHONY: install run build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run app locally on port $(PORT)
	uv run python3 -m uvicorn server:app --host 0.0.0.0 --port $(PORT)

build: ## Build container image  (APP_IMAGE, BUILD_PLATFORM)
	docker buildx build --platform $(BUILD_PLATFORM) -t $(APP_IMAGE) .

push: ## Build and push container image to registry
	docker buildx build --no-cache --platform $(BUILD_PLATFORM) -t $(APP_IMAGE) --push .

request: ## POST /haiku with a non-secret topic to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/haiku \
	  -H 'Content-Type: application/json' \
	  -d '{"topic":"cherry blossoms in spring"}' | python3 -m json.tool

request-secret: ## POST /haiku with a secret topic (redacted by OpenPipeline)
	curl -s -X POST http://localhost:$(PORT)/haiku \
	  -H 'Content-Type: application/json' \
	  -d '{"topic":"the secret launch codes"}' | python3 -m json.tool

request-all: ## Exercise both the redacted and non-redacted paths
	@$(MAKE) request-secret
	@echo
	@$(MAKE) request
