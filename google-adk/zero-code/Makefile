SHELL            := /bin/bash
-include .env

PORT             ?= 8000

# Zero-code instrumentation config. opentelemetry-instrument reads these and
# builds the SDK providers before app.py is imported.
OTEL_SERVICE_NAME                                  ?= google-adk-zero-code
OTEL_TRACES_EXPORTER                               ?= otlp
OTEL_METRICS_EXPORTER                              ?= otlp
OTEL_LOGS_EXPORTER                                 ?= none
OTEL_EXPORTER_OTLP_PROTOCOL                        ?= http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT                        ?= $(OTEL_ENDPOINT)
OTEL_EXPORTER_OTLP_HEADERS                         ?= Authorization=Api-Token $(DT_API_TOKEN)

# Only used by `make run-collector`. The app talks to the collector over plain
# HTTP and the collector holds the Dynatrace credentials, so these are the
# collector's own egress settings, not the app's.
DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com

# Bindplane Distro for OpenTelemetry (BDOT) collector.
override COLLECTOR_IMAGE     := ghcr.io/observiq/bindplane-agent:1.107.0
override COLLECTOR_CONTAINER := otel-collector
# Dynatrace OTLP metric ingest accepts delta temporality only (cumulative -> HTTP 400).
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE  ?= delta
# Without this, ADK and google-genai emit older gen_ai.* semantics.
OTEL_SEMCONV_STABILITY_OPT_IN                      ?= gen_ai_latest_experimental
# SPAN_ONLY keeps message content on span attributes. Dynatrace reads
# gen_ai.input.messages / gen_ai.output.messages there and cannot see them
# if they are emitted as log events instead.
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT ?= SPAN_ONLY

export

.PHONY: install run run-collector stop logs build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run app locally on port $(PORT) under opentelemetry-instrument
	uv run opentelemetry-instrument python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

run-collector: ## Start the OTel Collector, then run the app on port $(PORT) exporting through it
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 OTEL_EXPORTER_OTLP_HEADERS= \
	  uv run opentelemetry-instrument python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

stop: ## Stop and remove the OTel collector container
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

_collector:
	@if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	  echo "Collector already running, stopping it first..."; \
	  docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER); \
	fi; \
	echo "Starting collector ($(CONFIG)) -> $(DT_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4318:4318 \
	  -v $$(pwd)/$(CONFIG):/etc/otel/config.yaml:ro \
	  -e DT_ENDPOINT=$(DT_ENDPOINT) \
	  -e DT_API_TOKEN=$(DT_API_TOKEN) \
	  $(COLLECTOR_IMAGE) --config=/etc/otel/config.yaml && \
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

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /research to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/research \
	  -H 'Content-Type: application/json' \
	  -d '{"topic":"Attention is All You Need"}'
