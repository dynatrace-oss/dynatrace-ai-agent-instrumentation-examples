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
# Dynatrace OTLP metric ingest accepts delta temporality only (cumulative -> HTTP 400).
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE  ?= delta
# Without this, ADK and google-genai emit older gen_ai.* semantics.
OTEL_SEMCONV_STABILITY_OPT_IN                      ?= gen_ai_latest_experimental
# SPAN_ONLY keeps message content on span attributes. Dynatrace reads
# gen_ai.input.messages / gen_ai.output.messages there and cannot see them
# if they are emitted as log events instead.
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT ?= SPAN_ONLY

export

.PHONY: install run build push request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run app locally on port $(PORT) under opentelemetry-instrument
	uv run opentelemetry-instrument python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## POST /research to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/research \
	  -H 'Content-Type: application/json' \
	  -d '{"topic":"Attention is All You Need"}'
