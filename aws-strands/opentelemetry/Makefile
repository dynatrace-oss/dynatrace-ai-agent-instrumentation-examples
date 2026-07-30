SHELL            := /bin/bash
-include .env
export

DT_ENDPOINT      ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN     ?= dt0c01.*****

# Bindplane Distro for OpenTelemetry (BDOT) collector. v1.104.0 tracks OTel
# contrib v0.156.0 and bundles the signaltometrics connector used to derive
# gen_ai.client.token.usage from span attributes — that connector is NOT in the
# Dynatrace collector distro, so this demo runs Bindplane. Pinned so a version
# bump surfaces metric-derivation regressions in the e2e test.
override COLLECTOR_IMAGE     := ghcr.io/observiq/bindplane-agent:1.104.0
override COLLECTOR_CONTAINER := otel-collector

# Downstream 'appointments' service the create_appointment tool calls.
APPOINTMENTS_PORT    ?= 8081
APPT_OTEL_ENDPOINT   ?= http://localhost:4318
APPT_OTEL_HEADERS    ?=
APPT_SERVICE_NAME    ?= aws-strands/appointments-service

.PHONY: install run run-openpipeline build push request stop logs help _appointments _collector

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	uv sync

run: ## Start collector + appointments service + run the Strands agent demo
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	@$(MAKE) _appointments
	uv run python3 main.py

run-openpipeline: ## Run app directly to Dynatrace (no collector) [requires OpenPipeline deployed]
	@$(MAKE) _appointments \
	  APPT_OTEL_ENDPOINT=$(DT_ENDPOINT)/api/v2/otlp \
	  APPT_OTEL_HEADERS="Authorization=Api-Token $(DT_API_TOKEN)"
	@OTEL_SERVICE_NAME=aws-strands/opentelemetry-openpipeline \
	  OTEL_EXPORTER_OTLP_ENDPOINT=$(DT_ENDPOINT)/api/v2/otlp \
	  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $(DT_API_TOKEN)" \
	  uv run python3 main.py

build: ## Not applicable — no container defined for this demo
	@echo "build: no Dockerfile for this demo"

push: ## Not applicable — no container defined for this demo
	@echo "push: no Dockerfile for this demo"

request: ## Not applicable — this demo runs as a CLI, not an HTTP server
	@echo "request: this demo runs as a CLI script, not an HTTP server; use 'make run' instead"

stop: ## Stop the appointments service and remove the OTel collector container
	-@[ -f appointments.pid ] && kill $$(cat appointments.pid) 2>/dev/null && echo "Stopped appointments service" || true
	-@rm -f appointments.pid
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

# ---------------------------------------------------------------------------
# Internal targets
# ---------------------------------------------------------------------------
_appointments:
	@echo "Starting appointments service on 127.0.0.1:$(APPOINTMENTS_PORT) (traces -> $(APPT_OTEL_ENDPOINT))"
	@OTEL_EXPORTER_OTLP_ENDPOINT="$(APPT_OTEL_ENDPOINT)" \
	  OTEL_EXPORTER_OTLP_HEADERS="$(APPT_OTEL_HEADERS)" \
	  APPOINTMENTS_SERVICE_NAME="$(APPT_SERVICE_NAME)" \
	  uv run python3 -m uvicorn appointment_service:app \
	    --host 127.0.0.1 --port $(APPOINTMENTS_PORT) > appointments.log 2>&1 & \
	  echo $$! > appointments.pid
	@for i in $$(seq 1 15); do \
	  if curl -sf http://127.0.0.1:$(APPOINTMENTS_PORT)/api/v1/random >/dev/null 2>&1; then \
	    echo "Appointments service is up"; exit 0; \
	  fi; \
	  echo "  ... ($$i/15)"; sleep 1; \
	done; \
	echo "ERROR: appointments service did not become ready"; cat appointments.log; exit 1

_collector:
	@echo "Pulling collector image $(COLLECTOR_IMAGE) (may be slow on a cold runner)..." && \
	docker pull $(COLLECTOR_IMAGE) && \
	if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
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
	for i in $$(seq 1 30); do \
	  if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	    echo "Collector is up"; exit 0; \
	  fi; \
	  STATUS=$$(docker inspect -f '{{.State.Status}}' $(COLLECTOR_CONTAINER) 2>/dev/null); \
	  if [ "$$STATUS" = "exited" ]; then \
	    echo "ERROR: collector crashed — logs:"; docker logs $(COLLECTOR_CONTAINER); exit 1; \
	  fi; \
	  echo "  ... ($$i/30)"; sleep 2; \
	done; \
	echo "ERROR: collector did not become ready"; docker logs $(COLLECTOR_CONTAINER); exit 1
