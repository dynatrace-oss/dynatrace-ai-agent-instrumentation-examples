SHELL := /bin/bash

-include .env

DT_ENDPOINT ?=
DT_INGEST_TOKEN ?=
CLAUDE_CODE_VERSION ?= latest

override COLLECTOR_IMAGE := ghcr.io/observiq/bindplane-agent:1.108.0
override COLLECTOR_CONTAINER := claude-code-otel-collector

.PHONY: install run run-collector stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install: ## Install Claude Code CLI
	npm install --global @anthropic-ai/claude-code@$(CLAUDE_CODE_VERSION)

run: ## Run one headless Claude turn with telemetry sent directly to Dynatrace
	@test -n "$(DT_ENDPOINT)" || { echo "ERROR: set DT_ENDPOINT" >&2; exit 1; }
	@test -n "$(DT_INGEST_TOKEN)" || { echo "ERROR: set DT_INGEST_TOKEN" >&2; exit 1; }
	@$(MAKE) _run OTEL_EXPORTER_OTLP_ENDPOINT="$(DT_ENDPOINT)/api/v2/otlp" OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $(DT_INGEST_TOKEN)"

run-collector: ## Start collector enrichment and run one headless Claude turn
	@$(MAKE) _collector
	@$(MAKE) _run OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318" OTEL_EXPORTER_OTLP_HEADERS=""

_run:
	@test -n "$(ANTHROPIC_API_KEY)" -o -n "$(CLAUDE_CODE_OAUTH_TOKEN)" || { echo "ERROR: set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN" >&2; exit 1; }
	@CLAUDE_CODE_ENABLE_TELEMETRY=1 \
	 CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1 \
	 OTEL_TRACES_EXPORTER=otlp \
	 OTEL_METRICS_EXPORTER=otlp \
	 OTEL_LOGS_EXPORTER=otlp \
	 OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
	 OTEL_EXPORTER_OTLP_ENDPOINT="$(OTEL_EXPORTER_OTLP_ENDPOINT)" \
	 OTEL_EXPORTER_OTLP_HEADERS="$(OTEL_EXPORTER_OTLP_HEADERS)" \
	 OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta \
	 OTEL_METRIC_EXPORT_INTERVAL=1000 \
	 OTEL_LOGS_EXPORT_INTERVAL=1000 \
	 OTEL_LOG_USER_PROMPTS=1 \
	 claude -p --max-turns 1 --output-format text "Reply with exactly: claude-code-e2e-ok"

_collector:
	@test -n "$(DT_ENDPOINT)" || { echo "ERROR: set DT_ENDPOINT" >&2; exit 1; }
	@test -n "$(DT_INGEST_TOKEN)" || { echo "ERROR: set DT_INGEST_TOKEN" >&2; exit 1; }
	@docker rm -f $(COLLECTOR_CONTAINER) >/dev/null 2>&1 || true
	@docker run -d --name $(COLLECTOR_CONTAINER) -p 4317:4317 -p 4318:4318 \
		-v "$$(pwd)/collector/config.yaml:/etc/otel/config.yaml:ro" \
		-e DT_ENDPOINT="$(DT_ENDPOINT)" -e DT_API_TOKEN="$(DT_INGEST_TOKEN)" \
		$(COLLECTOR_IMAGE) --config=/etc/otel/config.yaml >/dev/null
	@for i in $$(seq 1 20); do \
		STATUS=$$(docker inspect -f '{{.State.Status}}' $(COLLECTOR_CONTAINER) 2>/dev/null || true); \
		if [ "$$STATUS" = "running" ]; then sleep 3; echo "Claude Code collector is ready"; exit 0; fi; \
		if [ "$$STATUS" = "exited" ]; then echo "ERROR: collector exited" >&2; docker logs $(COLLECTOR_CONTAINER); exit 1; fi; \
		sleep 1; \
	done; \
	echo "ERROR: collector did not become ready" >&2; docker logs $(COLLECTOR_CONTAINER); exit 1

stop: ## Stop and remove the collector
	-docker rm -f $(COLLECTOR_CONTAINER) >/dev/null 2>&1 || true

logs: ## Show collector logs
	docker logs $(COLLECTOR_CONTAINER)
