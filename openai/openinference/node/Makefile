SHELL            := /bin/bash
-include .env
export

APP_IMAGE        ?=
BUILD_PLATFORM   ?= linux/amd64
PORT             ?= 8000

DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN     ?= dt0c01.*****

# Host port for the collector's OTLP/HTTP receiver. Override if 4318 is taken.
OTLP_PORT        ?= 4318

# Dynatrace Bindplane Distribution of OpenTelemetry Collector (DBDOT). Bundles the
# span_metrics/signal_to_metrics connectors used to derive
# gen_ai.client.operation.duration / gen_ai.client.token.usage.
# Pinned so a version bump surfaces regressions in the e2e test.
override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-bindplane-otel-collector:1.2.0
override COLLECTOR_CONTAINER := bindplane-otel-collector

.PHONY: install run build push request stop logs help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Node.js dependencies and compile TypeScript
	npm ci
	npm run build

run: ## Start collector + app locally on port $(PORT)  (collector maps gen_ai.* and derives metrics)
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	@OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:$(OTLP_PORT) \
	  OTEL_EXPORTER_OTLP_HEADERS="" \
	  PORT=$(PORT) \
	  npm start

build: ## Build container image  (APP_IMAGE, BUILD_PLATFORM)
	docker buildx build --platform $(BUILD_PLATFORM) -t $(APP_IMAGE) .

push: ## Build and push container image to registry
	docker buildx build --no-cache --platform $(BUILD_PLATFORM) -t $(APP_IMAGE) --push .

request: ## POST /haiku to localhost:$(PORT)
	curl -s -X POST http://localhost:$(PORT)/haiku \
	  -H 'Content-Type: application/json' \
	  -d '{"topic":"e2e test"}' | python3 -m json.tool

# ---------------------------------------------------------------------------
# Internal targets
# ---------------------------------------------------------------------------
_collector:
	@if docker ps -a --filter name=$(COLLECTOR_CONTAINER) -q | grep -q .; then \
	  echo "Collector container exists, removing it first..."; \
	  docker rm -f $(COLLECTOR_CONTAINER) >/dev/null; \
	fi; \
	echo "Starting collector ($(CONFIG)) -> $(DT_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p $(OTLP_PORT):4318 \
	  -v $$(pwd)/$(CONFIG):/etc/otelcol/otel-collector-config.yaml:ro \
	  -e DT_ENDPOINT=$(DT_ENDPOINT) \
	  -e DT_API_TOKEN=$(DT_API_TOKEN) \
	  $(COLLECTOR_IMAGE) --config=/etc/otelcol/otel-collector-config.yaml || \
	  { echo "ERROR: docker run failed"; exit 1; }; \
	(docker logs -f $(COLLECTOR_CONTAINER) > collector.log 2>&1 &); \
	echo "Collector logs -> collector.log"; \
	until curl -s -o /dev/null http://localhost:$(OTLP_PORT)/v1/traces -X POST -H "Content-Type: application/json" -d '{}'; do \
	  STATUS=$$(docker inspect -f '{{.State.Status}}' $(COLLECTOR_CONTAINER) 2>/dev/null); \
	  if [ "$$STATUS" = "exited" ]; then echo "ERROR: collector crashed, logs:"; docker logs $(COLLECTOR_CONTAINER); exit 1; fi; \
	  echo "  waiting for collector..."; sleep 1; \
	done; \
	echo "Collector is up"

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
stop: ## Stop and remove the OTel collector container
	docker rm -f $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log
