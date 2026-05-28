SHELL               := /bin/bash
COLLECTOR_IMAGE     := otel/opentelemetry-collector-contrib:0.153.0
COLLECTOR_CONTAINER := otel-collector

.PHONY: run run-openpipeline stop logs deploy-openpipeline install help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

# ---------------------------------------------------------------------------
# run: collector applies OpenInference → gen_ai.* transforms locally
# ---------------------------------------------------------------------------
run: ## Start collector (transform mode) + app  [no OpenPipeline needed]
	@$(MAKE) _collector CONFIG=otel-collector-config.yaml
	@source .env && \
	  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
	  OTEL_EXPORTER_OTLP_HEADERS="" \
	  python3 app.py

# ---------------------------------------------------------------------------
# run-openpipeline: app sends directly to Dynatrace — OpenPipeline transforms
# Deploy first with: make deploy-openpipeline
# ---------------------------------------------------------------------------
run-openpipeline: ## Run app directly to Dynatrace  [requires OpenPipeline in Dynatrace]
	@source .env && \
	  OTEL_EXPORTER_OTLP_ENDPOINT=$$DT_ENDPOINT/api/v2/otlp \
	  OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $$DT_API_TOKEN" \
	  python3 app.py

# ---------------------------------------------------------------------------
# Internal targets
# ---------------------------------------------------------------------------
_collector:
	@if docker ps --filter name=$(COLLECTOR_CONTAINER) --filter status=running -q | grep -q .; then \
	  echo "Collector already running — stopping it first..."; \
	  docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER); \
	fi; \
	source .env && \
	echo "Starting collector ($(CONFIG)) -> $$DT_ENDPOINT" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4318:4318 \
	  -v $$(pwd)/$(CONFIG):/collector-config.yaml:ro \
	  -e DT_ENDPOINT=$$DT_ENDPOINT \
	  -e DT_API_TOKEN=$$DT_API_TOKEN \
	  $(COLLECTOR_IMAGE) --config=/collector-config.yaml && \
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

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
stop: ## Stop and remove the OTel collector container
	docker stop $(COLLECTOR_CONTAINER) && docker rm $(COLLECTOR_CONTAINER)

logs: ## Tail collector logs
	@touch collector.log && tail -F collector.log

deploy-openpipeline: ## Deploy OpenPipeline config + routing to Dynatrace (reads .env)
	@source .env && DT_ENDPOINT=$$DT_ENDPOINT DT_API_TOKEN=$$DT_API_TOKEN \
	  bash deploy-openpipeline.sh
