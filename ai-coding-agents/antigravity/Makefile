SHELL := /bin/bash
-include .env
export

VENV := .venv
PY   := $(VENV)/bin/python

# Dynatrace OTLP base URL. e2e CI supplies DT_ENDPOINT (tenant root) instead, so
# fall back to deriving it.
DT_ENDPOINT      ?=
DT_OTEL_ENDPOINT ?= $(if $(DT_ENDPOINT),$(DT_ENDPOINT)/api/v2/otlp,)

# Bindplane Distro for OpenTelemetry. Used only by `make run-collector`, for the
# span_metrics connector that derives the GenAI agent/tool duration metrics.
override COLLECTOR_IMAGE     := ghcr.io/observiq/bindplane-agent:1.107.0
override COLLECTOR_CONTAINER := antigravity-otel-collector

.PHONY: install run run-collector stop logs build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -r requirements.txt

run: ## Run the agent once, exporting traces straight to Dynatrace
	OTEL_EXPORTER_OTLP_ENDPOINT="$(DT_OTEL_ENDPOINT)" $(PY) app.py

run-collector: ## Start the OTel Collector, then run the agent exporting through it
	@$(MAKE) _collector
	OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 $(PY) app.py

stop: ## Stop and remove the OTel Collector container
	-docker rm -f $(COLLECTOR_CONTAINER) >/dev/null 2>&1 || true

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

_collector:
	@test -n "$(DT_OTEL_ENDPOINT)" || { echo "ERROR: set DT_OTEL_ENDPOINT (or DT_ENDPOINT)"; exit 1; }
	@test -n "$(DT_API_TOKEN)" || { echo "ERROR: set DT_API_TOKEN"; exit 1; }
	@docker rm -f $(COLLECTOR_CONTAINER) >/dev/null 2>&1 || true; \
	echo "Starting collector -> $(DT_OTEL_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4317:4317 -p 4318:4318 \
	  -v $$(pwd)/collector.yaml:/etc/otel/config.yaml:ro \
	  -e DT_OTEL_ENDPOINT="$(DT_OTEL_ENDPOINT)" \
	  -e DT_API_TOKEN="$(DT_API_TOKEN)" \
	  $(COLLECTOR_IMAGE) && \
	docker logs -f $(COLLECTOR_CONTAINER) > collector.log 2>&1 & \
	echo "Collector logs -> collector.log" && \
	for i in $$(seq 1 15); do \
	  if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	    echo "Collector is up"; exit 0; \
	  fi; \
	  STATUS=$$(docker inspect -f '{{.State.Status}}' $(COLLECTOR_CONTAINER) 2>/dev/null); \
	  if [ "$$STATUS" = "exited" ]; then \
	    echo "ERROR: collector crashed; logs:"; docker logs $(COLLECTOR_CONTAINER); exit 1; \
	  fi; \
	  echo "  ... ($$i/15)"; sleep 2; \
	done; \
	echo "ERROR: collector did not become ready"; docker logs $(COLLECTOR_CONTAINER); exit 1

build: ## Not applicable (no container defined for this demo)
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable (no container defined for this demo)
	@echo "push: no Dockerfile for this demo"

request: ## Not applicable (this demo is a CLI agent, not an HTTP server)
	@echo "request: this demo is a CLI agent; use 'make run'"
