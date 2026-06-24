SHELL               := /bin/bash

# ---------------------------------------------------------------------------
# Configuration — set in .env (KEY=value format, no export, no quotes)
# ---------------------------------------------------------------------------
-include .env
export

DT_ENDPOINT         ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN        ?= dt0c01.*****

APP_IMAGE           ?=
BUILD_PLATFORM      ?= linux/amd64

NODE                := node

override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.50.0
override COLLECTOR_CONTAINER := otel-collector
override COLLECTOR_CONFIG    := $(abspath ../opentelemetry/otel-collector-config.yaml)

.PHONY: run run-openpipeline build push request stop logs install help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Node.js dependencies
	npm install

# ---------------------------------------------------------------------------
# run: collector applies langfuse.* -> gen_ai.* transforms locally
# ---------------------------------------------------------------------------
run: ## Build app, start collector (transform mode) + run  [no OpenPipeline needed]
	@$(MAKE) _build
	@$(MAKE) _collector
	@echo "Waiting for collector port to be ready..."
	@sleep 3
	@until curl -s -o /dev/null -w '' http://localhost:4318/v1/traces -X POST -H "Content-Type: application/json" -d '{}' 2>/dev/null; do \
      echo "  waiting..."; sleep 1; \
    done
	@echo "Collector port is responding"
	@OTEL_SERVICE_NAME=langfuse-node \
	  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
	  OTEL_EXPORTER_OTLP_HEADERS="" \
	  $(NODE) dist/index.js

# ---------------------------------------------------------------------------
# run-openpipeline: app sends directly to Dynatrace — OpenPipeline transforms
# Deploy first with the processors in ../opentelemetry/openpipeline-langfuse.yaml.
# Routing matcher: isNotNull(langfuse.observation.type)
# ---------------------------------------------------------------------------
run-openpipeline: ## Build app + run directly to Dynatrace  [requires OpenPipeline in Dynatrace]
	@$(MAKE) _build
	@OTEL_SERVICE_NAME=langfuse-node \
	  OTEL_EXPORTER_OTLP_ENDPOINT=$(DT_ENDPOINT)/api/v2/otlp \
	  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $(DT_API_TOKEN)" \
	  $(NODE) dist/index.js

# ---------------------------------------------------------------------------
# Internal targets
# ---------------------------------------------------------------------------
_build:
	npm run build

_collector:
	@if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	  echo "Collector already running — stopping it first..."; \
	  docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER); \
	fi; \
	echo "Starting collector -> $(DT_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4318:4318 \
	  -v $(COLLECTOR_CONFIG):/etc/otelcol/otel-collector-config.yaml:ro \
	  -e DT_ENDPOINT=$(DT_ENDPOINT) \
	  -e DT_API_TOKEN=$(DT_API_TOKEN) \
	  $(COLLECTOR_IMAGE) --config=/etc/otelcol/otel-collector-config.yaml && \
	docker logs -f $(COLLECTOR_CONTAINER) > collector.log 2>&1 & \
	echo "Collector logs -> collector.log" && \
	for i in $$(seq 1 15); do \
	  if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	    echo "Collector is up"; exit 0; \
	  fi; \
	  STATUS=$$(docker inspect -f '{{.State.Status}}' $(COLLECTOR_CONTAINER) 2>/dev/null); \
	  if [ "$$STATUS" = "exited" ]; then \
	    echo "ERROR: collector crashed — logs:"; docker logs $(COLLECTOR_CONTAINER); exit 1; \
	  fi; \
	  echo "  ... ($$i/15)"; sleep 2; \
	done; \
	echo "ERROR: collector did not become ready"; docker logs $(COLLECTOR_CONTAINER); exit 1

build: ## Build container image  (APP_IMAGE, BUILD_PLATFORM)
	docker buildx build --platform $(BUILD_PLATFORM) -t $(APP_IMAGE) .

push: ## Build and push container image to registry
	docker buildx build --no-cache --platform $(BUILD_PLATFORM) -t $(APP_IMAGE) --push .

request: ## Run the app once against a running collector
	@$(MAKE) _build
	@OTEL_SERVICE_NAME=langfuse-node \
	  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
	  OTEL_EXPORTER_OTLP_HEADERS="" \
	  $(NODE) dist/index.js

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
stop: ## Stop and remove the OTel collector container
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log
