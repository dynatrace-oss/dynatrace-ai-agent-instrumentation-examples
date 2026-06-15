PYTHON ?= python3
VENV ?= .venv

.PHONY: install run

install:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -r requirements.txt

run:
	@if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	. $(VENV)/bin/activate && python app.py
