.PHONY: help install run clean

help:
	@printf "make install  Create/update .venv from pyproject.toml with uv\n"
	@printf "make run      Load .env and run through the uv project environment\n"
	@printf "make clean    Remove the virtual environment and Python caches\n"

install:
	uv sync

run:
	@test -f .env || (echo "Copy .env.sample to .env and fill in the values" && exit 1)
	@set -a; . ./.env; set +a; uv run --no-sync python app.py

clean:
	rm -rf .venv __pycache__
