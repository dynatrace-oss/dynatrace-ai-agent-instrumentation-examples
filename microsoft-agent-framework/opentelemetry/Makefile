SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000

DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN     ?= dt0c01.*****

# Bindplane Distro for OpenTelemetry (BDOT) collector. Used only by
# `make run-collector` to derive the GenAI agent/tool/workflow duration metrics
# from spans via the spanmetrics connector.
override COLLECTOR_IMAGE     := ghcr.io/observiq/bindplane-agent:1.105.1
override COLLECTOR_CONTAINER := otel-collector

.PHONY: install run run-collector stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run the agent app, exporting straight to Dynatrace
	uv run python3 app.py

run-collector: ## Start the OTel Collector, then run the app exporting through it
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	OTEL_COLLECTOR_ENDPOINT=http://localhost:4318 uv run python3 app.py

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
