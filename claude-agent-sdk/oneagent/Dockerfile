FROM --platform=linux/amd64 python:3.15-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# The claude-agent-sdk wheel bundles the Claude Code CLI binary, so no Node.js install is needed.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py server.py ./

# The CLI writes session state under $HOME; run as a non-root user with a writable home.
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000

CMD ["uv", "run", "python3", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
