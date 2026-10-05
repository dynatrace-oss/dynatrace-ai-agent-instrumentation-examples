SHELL               := /bin/bash
-include .env
export

DT_ENDPOINT         ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN        ?= dt0c01.*****
OTEL_SERVICE_NAME   ?= llama-stack/opentelemetry
PORT                ?= 8000

.PHONY: install run request help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Run app on port $(PORT), exporting traces and metrics directly to Dynatrace
	@OTEL_TRACES_EXPORTER=otlp \
	  OTEL_METRICS_EXPORTER=otlp \
	  OTEL_LOGS_EXPORTER=none \
	  OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
	  OTEL_EXPORTER_OTLP_ENDPOINT=$(DT_ENDPOINT)/api/v2/otlp \
	  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $(DT_API_TOKEN)" \
	  OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta \
	  OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental \
	  OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=span_only \
	  uv run opentelemetry-instrument python3 -m uvicorn app:app --host 0.0.0.0 --port $(PORT)

request: ## POST /haiku to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/haiku
