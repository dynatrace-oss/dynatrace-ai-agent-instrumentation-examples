# OpenAI + OneAgent Demo

Demonstrates tracing OpenAI SDK API calls with Dynatrace via OneAgent auto-instrumentation.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- OpenAI API key (`OPENAI_API_KEY`)
- Dynatrace OneAgent installed on the host

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install` — install dependencies
3. `make run` — start the app on port 8000
4. `make request` — send a test haiku request (in a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `MODEL` | No | `gpt-4o` | Model to use |
| `OPENAI_API_BASE` | No | — | Custom API base URL (e.g. Azure OpenAI endpoint) |
| `OPENAI_API_VERSION` | No | — | API version (required for Azure OpenAI) |
| `DT_APPLICATIONID` | No | `openai-oneagent` | OneAgent application identifier — ensures a distinct Smartscape SERVICE entity when multiple services share the same host |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make help` | Show all available targets |
