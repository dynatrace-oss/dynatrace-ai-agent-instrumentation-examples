.PHONY: help run clean

help:
	@printf "Install dependencies from requirements.txt in a virtual environment.\n"
	@printf "make run      Load .env and run the example\n"
	@printf "make clean    Remove the virtual environment\n"

run:
	@test -f .env || (echo "Copy .env.sample to .env and fill in the values" && exit 1)
	@test -x .venv/bin/python || (echo "Create .venv and install requirements.txt first" && exit 1)
	@set -a; . ./.env; set +a; .venv/bin/python app.py

clean:
	rm -rf .venv
