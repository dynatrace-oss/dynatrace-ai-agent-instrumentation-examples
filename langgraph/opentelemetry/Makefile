SHELL               := /bin/bash
-include .env
export

PORT                ?= 8000
DT_ENDPOINT         ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN        ?= dt0c01.*****

override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.51.0
override COLLECTOR_CONTAINER := langgraph-otel-collector

.PHONY: install run build push request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

# run: start the Dynatrace collector (redacts secrets) then the app, which
# exports to the collector at localhost:4318 instead of straight to Dynatrace.
run: ## Start collector + app on port $(PORT)
	@$(MAKE) _collector
	@echo "Waiting for collector port to be ready..."
	@until curl -s -o /dev/null http://localhost:4318/v1/traces -X POST -H "Content-Type: application/json" -d '{}' 2>/dev/null; do \
	  echo "  waiting..."; sleep 1; \
	done
	@echo "Collector port is responding"
	@OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
	  uv run python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /haiku with a non-secret topic to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/haiku \
	  -H "Content-Type: application/json" \
	  -d '{"topic": "cherry blossoms in spring"}'

stop: ## Stop and remove the OTel collector container
	@docker stop $(COLLECTOR_CONTAINER) >/dev/null 2>&1 && docker rm $(COLLECTOR_CONTAINER) >/dev/null 2>&1 || true

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

_collector:
	@if docker ps -a --filter name=$(COLLECTOR_CONTAINER) -q | grep -q .; then \
	  echo "Removing existing collector container..."; \
	  docker rm -f $(COLLECTOR_CONTAINER) >/dev/null 2>&1; \
	fi; \
	echo "Starting collector -> $(DT_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4318:4318 \
	  -v $$(pwd)/otel-collector-config.yaml:/etc/otelcol/otel-collector-config.yaml:ro \
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
