SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN     ?= dt0c01.*****

# Bindplane Distro for OpenTelemetry (BDOT) collector. v1.104.0 tracks OTel
# contrib v0.156.0. Used only by `make run-collector` to derive
# gen_ai.client.operation.duration from spans via the span_metrics connector.
override COLLECTOR_IMAGE     := ghcr.io/observiq/bindplane-agent:1.106.0
override COLLECTOR_CONTAINER := otel-collector

.PHONY: install run run-collector build push request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run the backend, exporting straight to Dynatrace [needs OpenPipeline for duration]
	PYTHONPATH=backend uv run python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $(PORT)

run-collector: ## Start the OTel Collector, then run the backend exporting through it
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	OTEL_COLLECTOR_ENDPOINT=http://localhost:4318 \
	  PYTHONPATH=backend uv run python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $(PORT)

stop: ## Stop and remove the OTel collector container
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

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

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /chat to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/chat \
	  -H 'Content-Type: application/json' \
	  -d '{"message":"Write a haiku about the ocean"}' | python3 -m json.tool
