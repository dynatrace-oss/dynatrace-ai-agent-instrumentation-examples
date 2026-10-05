# Shared OTel Collector targets for the litellm/opentelemetry demos.
# Include from a subdirectory Makefile and call: $(MAKE) _collector CONFIG=<path>

override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.56.0
COLLECTOR_CONTAINER          ?= otel-collector

.PHONY: _collector _collector-stop

_collector:
	@if docker ps -a --filter name=^/$(COLLECTOR_CONTAINER)$$ -q | grep -q .; then \
	  echo "Removing existing $(COLLECTOR_CONTAINER) container..."; \
	  docker rm -f $(COLLECTOR_CONTAINER) >/dev/null; \
	fi; \
	echo "Starting collector ($(CONFIG)) -> $(DT_ENDPOINT)" && \
	docker run -d \
	  --name $(COLLECTOR_CONTAINER) \
	  -p 4317:4317 \
	  -p 4318:4318 \
	  -v $(abspath $(CONFIG)):/etc/otelcol/otel-collector-config.yaml:ro \
	  -e DT_ENDPOINT=$(DT_ENDPOINT) \
	  -e DT_API_TOKEN=$(DT_API_TOKEN) \
	  $(COLLECTOR_IMAGE) --config=/etc/otelcol/otel-collector-config.yaml && \
	(docker logs -f $(COLLECTOR_CONTAINER) > collector.log 2>&1 &) && \
	echo "Collector logs -> collector.log" && \
	for i in $$(seq 1 15); do \
	  if docker ps --filter name=^/$(COLLECTOR_CONTAINER)$$ --filter status=running -q | grep -q .; then \
	    echo "Collector is up"; exit 0; \
	  fi; \
	  STATUS=$$(docker inspect -f '{{.State.Status}}' $(COLLECTOR_CONTAINER) 2>/dev/null); \
	  if [ "$$STATUS" = "exited" ]; then \
	    echo "ERROR: collector crashed, logs:"; docker logs $(COLLECTOR_CONTAINER); exit 1; \
	  fi; \
	  echo "  ... ($$i/15)"; sleep 2; \
	done; \
	echo "ERROR: collector did not become ready"; docker logs $(COLLECTOR_CONTAINER); exit 1

_collector-stop:
	-@docker rm -f $(COLLECTOR_CONTAINER) >/dev/null 2>&1 || true
