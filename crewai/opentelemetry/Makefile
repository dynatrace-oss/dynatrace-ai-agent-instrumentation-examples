SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

# Only used by `make run-collector`. The app talks to the collector over plain
# HTTP and the collector holds the Dynatrace credentials, so these are the
# collector's own egress settings, not the app's.
DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN     ?= dt0c01.*****

# Used only by `make run-collector` to derive the GenAI agent and workflow
# duration metrics from spans via the span_metrics connector.
override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.53.1
override COLLECTOR_CONTAINER := crewai-otel-collector

.PHONY: install run run-collector stop logs build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run app locally on port $(PORT)
	uv run python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

run-collector: ## Start the OTel Collector, then run the app on port $(PORT) exporting through it
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	OTEL_ENDPOINT=http://localhost:4318 \
	  uv run python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

stop: ## Stop and remove the OTel collector container
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

_collector:
	@if docker ps -a --filter name=$(COLLECTOR_CONTAINER) -q | grep -q .; then \
	  echo "Removing existing collector container..."; \
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

request: ## POST /haiku to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/haiku
