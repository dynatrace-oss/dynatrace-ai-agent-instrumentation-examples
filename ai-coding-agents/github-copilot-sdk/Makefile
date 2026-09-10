SHELL               := /bin/bash

# ---------------------------------------------------------------------------
# Configuration: set in .env (KEY=value format, no export, no quotes)
# ---------------------------------------------------------------------------
-include .env
export

# DT_ENDPOINT is the bare tenant URL; the e2e suite and the other demos set it.
DT_ENDPOINT         ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN        ?= dt0c01.*****
DT_OTEL_ENDPOINT    ?= $(DT_ENDPOINT)/api/v2/otlp

NODE                := node

# Port 4318 is often already taken (a local dynatrace-otel-collector, another
# demo's collector). Override OTLP_PORT if so; a conflicting listener silently
# swallows the agent's telemetry instead of failing.
OTLP_PORT           ?= 4318

COLLECTOR_IMAGE     ?= otel/opentelemetry-collector-contrib:0.140.0
COLLECTOR_CONTAINER ?= copilot-otel-collector
COLLECTOR_CONFIG    := $(abspath collector.yaml)

.PHONY: install build run request stop logs help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Node.js dependencies
	npm install

build: ## Compile TypeScript
	npm run build

# ---------------------------------------------------------------------------
# run: start the collector, then run the agent once with native telemetry on
# ---------------------------------------------------------------------------
run: ## Start collector + run the agent once
	@$(MAKE) build
	@$(MAKE) _collector
	@echo "Waiting for collector OTLP port..."
	@until curl -s -o /dev/null http://localhost:$(OTLP_PORT)/v1/traces -X POST \
	    -H "Content-Type: application/json" -d '{}' 2>/dev/null; do \
	  echo "  waiting..."; sleep 1; \
	done
	@echo "Collector is up"
	@COPILOT_OTLP_ENDPOINT=http://localhost:$(OTLP_PORT) $(NODE) dist/index.js

request: ## Run the agent once against an already-running collector
	@$(MAKE) build
	@COPILOT_OTLP_ENDPOINT=http://localhost:$(OTLP_PORT) $(NODE) dist/index.js

_collector:
	@if [[ "$(DT_OTEL_ENDPOINT)" == *your-tenant* || "$(DT_API_TOKEN)" == "dt0c01.*****" ]]; then \
	  echo "ERROR: DT_ENDPOINT / DT_API_TOKEN are unset; the collector would ship to a placeholder host."; \
	  echo "       Set them in .env or the environment before running."; exit 1; \
	fi
	@if lsof -nP -iTCP:$(OTLP_PORT) -sTCP:LISTEN >/dev/null 2>&1 && \
	    ! docker ps --filter name=$(COLLECTOR_CONTAINER) -q | grep -q .; then \
	  echo "ERROR: port $(OTLP_PORT) is already in use by another process:"; \
	  lsof -nP -iTCP:$(OTLP_PORT) -sTCP:LISTEN; \
	  echo "       It would swallow the agent's telemetry. Stop it or set OTLP_PORT=<free-port>."; \
	  exit 1; \
	fi
	@if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	  echo "Collector already running, stopping it first..."; \
	  docker stop $(COLLECTOR_CONTAINER) >/dev/null && docker rm $(COLLECTOR_CONTAINER) >/dev/null; \
	fi; \
	echo "Starting collector -> $(DT_OTEL_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p $(OTLP_PORT):4318 \
	  -v $(COLLECTOR_CONFIG):/etc/otelcol-contrib/config.yaml:ro \
	  -e DT_OTEL_ENDPOINT=$(DT_OTEL_ENDPOINT) \
	  -e DT_API_TOKEN=$(DT_API_TOKEN) \
	  $(COLLECTOR_IMAGE) --config=/etc/otelcol-contrib/config.yaml >/dev/null && \
	docker logs -f $(COLLECTOR_CONTAINER) > collector.log 2>&1 & \
	echo "Collector logs -> collector.log" && \
	for i in $$(seq 1 15); do \
	  if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	    echo "Collector is up"; exit 0; \
	  fi; \
	  STATUS=$$(docker inspect -f '{{.State.Status}}' $(COLLECTOR_CONTAINER) 2>/dev/null); \
	  if [ "$$STATUS" = "exited" ]; then \
	    echo "ERROR: collector crashed, logs:"; docker logs $(COLLECTOR_CONTAINER); exit 1; \
	  fi; \
	  echo "  ... ($$i/15)"; sleep 2; \
	done; \
	echo "ERROR: collector did not become ready"; docker logs $(COLLECTOR_CONTAINER); exit 1

stop: ## Stop and remove the OTel collector container
	-docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log
