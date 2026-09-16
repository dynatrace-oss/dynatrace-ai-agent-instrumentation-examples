SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: help install run request clean

help:
	@printf "make install  Sync dependencies from pyproject.toml\n"
	@printf "make run      Start the API on http://localhost:8000\n"
	@printf "make request  Send a test request to POST /haiku\n"
	@printf "make clean    Remove generated files\n"

install:
	uv sync

run:
	@test -f .env || (echo "Copy .env.sample to .env and fill in the values" >&2; exit 1)
	@set -a; \
	source .env; \
	set +a; \
	uv run --no-sync uvicorn app:app --host 0.0.0.0 --port 8000

request:
	@curl --fail-with-body --show-error --silent \
		-X POST http://localhost:8000/haiku \
		-H 'Content-Type: application/json' \
		-d '{"topic":"e2e test"}' \
		| python3 -m json.tool

clean:
	rm -rf .venv __pycache__ .pytest_cache