.PHONY: help install run stop logs request

N8N_URL ?= http://localhost:5678
WEBHOOK_PATH ?= e2e-trigger

# CI exports the tenant as DT_ENDPOINT; the compose stack reads DT_ENVIRONMENT_URL.
DT_ENVIRONMENT_URL ?= $(DT_ENDPOINT)

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.env:
	@if [ -n "$(DT_API_TOKEN)" ] && [ -n "$(DT_ENVIRONMENT_URL)" ]; then \
		sed -e "s|^DT_ENVIRONMENT_URL=.*|DT_ENVIRONMENT_URL=$(DT_ENVIRONMENT_URL)|" \
		    -e "s|^DT_API_TOKEN=.*|DT_API_TOKEN=$(DT_API_TOKEN)|" .env.sample > .env; \
	else \
		cp .env.sample .env; \
		echo "warning: DT_ENVIRONMENT_URL / DT_API_TOKEN not set — edit .env before running"; \
	fi

install: .env ## Pull the n8n, Postgres and collector images
	docker compose pull

run: .env ## Start n8n, Postgres and the OTel Collector in the background
	docker compose up -d --wait

stop: ## Stop everything and remove the volumes
	docker compose down -v --remove-orphans

logs: ## Tail the n8n and collector logs
	docker compose logs -f n8n collector

request: ## Trigger the webhook-based sample workflow
	curl -sS -X POST "$(N8N_URL)/webhook/$(WEBHOOK_PATH)" \
		-H 'Content-Type: application/json' \
		-d '{"topic": "observability"}'
