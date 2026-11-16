# OGX + OneAgent Demo

Runs [OGX](https://github.com/ogx-ai/ogx) (formerly Llama Stack, the runtime behind the GenAI Playground and GenAI Studio in Red Hat OpenShift AI 3.x) in library mode inside a FastAPI app, with inference served by a local Ollama, and traces it with Dynatrace OneAgent auto-instrumentation.

`POST /haiku` runs one turn of the OGX Responses API, its agent runtime. OGX's Ollama provider sends the model calls through the `openai` Python client to Ollama's OpenAI-compatible `/v1` endpoint, so OneAgent captures them with its OpenAI sensor. OneAgent has no OGX sensor, and OGX doesn't emit GenAI agent spans itself, so `invoke_agent` spans and `gen_ai.agent.name` are not expected.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Ollama running locally or accessible at `OLLAMA_URL`, with `MODEL` pulled
- Dynatrace OneAgent installed on the host

## Quick Start

1. Copy `.env.sample` to `.env` and fill in the values
2. `make install` (install dependencies)
3. `make run` (start the app on port 8000)
4. `make request` (send a test haiku request from a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_URL` | No | `http://localhost:11434/v1` | Ollama OpenAI-compatible endpoint |
| `MODEL` | No | `llama3.2` | Ollama model to use |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make help` | Show all available targets |

## OGX configuration

`config.yaml` is a minimal OGX distribution with the Responses API (`inline::builtin`), its required file, vector and tool providers, and the `remote::ollama` inference provider. Models are discovered from Ollama at startup and addressed as `ollama/<model>`.
