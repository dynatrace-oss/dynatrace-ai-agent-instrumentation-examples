SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
-include .env
export
.PHONY: help install run request clean

help:
	@printf "make install  Sync dependencies from pyproject.toml\n"
	@printf "make run      Start the API on http://localhost:8000\n"
	@printf "make request  Send a test request to POST /haiku\n"
	@printf "make clean    Remove generated files\n"

install:
	uv sync

run:
	@OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="$${DT_ENDPOINT}/api/v2/otlp/v1/traces" \
    	OTEL_EXPORTER_OTLP_TRACES_HEADERS="Authorization=Api-Token $${DT_API_TOKEN}" \
	  uv run --no-sync uvicorn app:app --host 0.0.0.0 --port 8000
request:
	@curl --fail-with-body --show-error --silent \
		-X POST http://localhost:8000/haiku \
		-H 'Content-Type: application/json' \
		-d '{"topic":"e2e test"}' \
		| python3 -m json.tool

clean:
	rm -rf .venv __pycache__ .pytest_cache

stop:
	@-pkill -f 'uvicorn app:app' 2>/dev/null || true