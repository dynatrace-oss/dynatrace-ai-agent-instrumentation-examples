FROM --platform=linux/amd64 python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py server.py ./

EXPOSE 8000

CMD ["uv", "run", "python3", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
