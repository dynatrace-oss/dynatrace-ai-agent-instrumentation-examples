SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000
PYTHON           := $(shell [ -f .venv/bin/python ] && echo .venv/bin/python || echo python3)

DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN     ?= dt0c01.*****

override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.50.0
override COLLECTOR_CONTAINER := otel-collector

.PHONY: install run build push request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	$(PYTHON) -m pip install -r requirements.txt

run: ## Start collector + run the AWS Bedrock tracing demo
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	$(PYTHON) main.py

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## Not applicable — this demo runs as a CLI, not an HTTP server
	@echo "request: this demo runs as a CLI script, not an HTTP server; use 'make run' instead"

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

stop: ## Stop and remove the OTel collector container
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log
