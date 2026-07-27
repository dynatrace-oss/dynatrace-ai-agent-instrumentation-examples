SHELL               := /bin/bash

# ---------------------------------------------------------------------------
# Configuration — set in .env (KEY=value format, no export, no quotes)
# ---------------------------------------------------------------------------
-include .env
export

DT_ENDPOINT         ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN        ?= dt0c01.*****

# Bindplane Distro for OpenTelemetry (BDOT) collector. Pinned for
# reproducibility; no special processors are needed — it runs as a plain
# OTel Collector that receives OTLP on 4318 and forwards to Dynatrace.
override COLLECTOR_IMAGE     := ghcr.io/observiq/bindplane-agent:1.104.0
override COLLECTOR_CONTAINER := bindplane-otel-collector

.PHONY: run run-direct request stop logs install help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

# ---------------------------------------------------------------------------
# run: app → local OTel collector → Dynatrace
# ---------------------------------------------------------------------------
run: ## Start OTel collector + run app  [recommended]
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	@echo "Waiting for collector port to be ready..."
	@sleep 3
	@until curl -s -o /dev/null -w '' http://localhost:4318/v1/traces -X POST -H "Content-Type: application/json" -d '{}' 2>/dev/null; do \
	  echo "  waiting..."; sleep 1; \
	done
	@echo "Collector port is responding"
	@OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
	  uv run python3 app.py

# ---------------------------------------------------------------------------
# run-direct: app → Dynatrace (no collector)
# ---------------------------------------------------------------------------
run-direct: ## Run app directly to Dynatrace  [no collector needed]
	@OTEL_EXPORTER_OTLP_ENDPOINT="" \
	  uv run python3 app.py

request: ## Run a haiku request through the running collector
	@OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
	  uv run python3 app.py

# ---------------------------------------------------------------------------
# Internal targets
# ---------------------------------------------------------------------------
_collector:
	@if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	  echo "Collector already running — stopping it first..."; \
	  docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER); \
	fi; \
	echo "Starting collector ($(CONFIG)) -> $(DT_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4318:4318 \
	  -v $$(pwd)/$(CONFIG):/etc/otel/config.yaml:ro \
	  -e DT_ENDPOINT=$(DT_ENDPOINT) \
	  -e DT_API_TOKEN=$(DT_API_TOKEN) \
	  $(COLLECTOR_IMAGE) && \
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

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
stop: ## Stop and remove the OTel collector container
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log
