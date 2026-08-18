SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN     ?= dt0c01.*****

# Dynatrace Distro for OpenTelemetry Collector. Used only by `make run-collector`
# to derive gen_ai.client.operation.duration and gen_ai.invoke_agent.duration from
# spans via the span_metrics connector. Pinned so a version bump is a visible diff.
override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.54.0
override COLLECTOR_CONTAINER := rum-otel-collector

# The collector run must report under a DIFFERENT service.name than the direct
# export run: otherwise the collector-derived durations and the OpenPipeline-derived
# durations land on the same series and double-count.
COLLECTOR_SERVICE_NAME ?= rum/opentelemetry-collector

.PHONY: install run run-collector stop build push request demo logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies for backend
	uv sync

run: ## Run the backend on port $(PORT), exporting straight to Dynatrace [needs OpenPipeline for the duration metrics]
	cd backend && uv run python3 -m uvicorn main:app --host 0.0.0.0 --port $(PORT)

run-collector: ## Start the OTel Collector, then run the backend exporting through it (derives the duration metrics locally)
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	cd backend && OTEL_COLLECTOR_ENDPOINT=http://localhost:4318 \
	  OTEL_SERVICE_NAME=$(COLLECTOR_SERVICE_NAME) \
	  uv run python3 -m uvicorn main:app --host 0.0.0.0 --port $(PORT)

stop: ## Stop the collector if one is running (the backend process is managed by the test runner)
	@docker rm -f $(COLLECTOR_CONTAINER) >/dev/null 2>&1 || true

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

_collector:
	@if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	  echo "Collector already running — stopping it first..."; \
	  docker rm -f $(COLLECTOR_CONTAINER) >/dev/null; \
	fi; \
	echo "Starting collector ($(CONFIG)) -> $(DT_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4318:4318 \
	  -v $$(pwd)/$(CONFIG):/etc/otelcol/otel-collector-config.yaml:ro \
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

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /api/ask to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/api/ask \
	  -H 'Content-Type: application/json' \
	  -d '{"question":"Who invented jazz?","conversation_id":"$(shell python3 -c \"import uuid; print(uuid.uuid4())\")"}' | python3 -m json.tool

demo: ## Run a browser session via Playwright — headed locally, headless in CI (backend must be running)
	uv sync --extra demo
	uv run playwright install chromium
	uv run python3 scripts/browser_demo.py
