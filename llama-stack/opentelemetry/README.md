# Llama Stack + OpenTelemetry Demo

Runs [Llama Stack](https://github.com/llamastack/llama-stack) in library mode inside a FastAPI app, with inference served by a local Ollama, and exports traces and metrics directly to Dynatrace over OTLP. Llama Stack is the runtime behind the GenAI Playground and GenAI Studio in Red Hat OpenShift AI 3.x.

Llama Stack creates almost no spans of its own and relies on OpenTelemetry auto-instrumentation. Its Ollama provider calls Ollama's OpenAI-compatible `/v1` endpoint through the `openai` Python client, so `opentelemetry-instrumentation-openai-v2` produces the `gen_ai.*` chat spans. Llama Stack's Responses runtime doesn't emit GenAI agent spans itself, so agent spans (`invoke_agent`, `gen_ai.agent.name`) are not expected.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Ollama running locally or accessible at `OLLAMA_URL`, with `MODEL` pulled
- A Dynatrace API token with `openTelemetryTrace.ingest` and `metrics.ingest` scopes

## Quick Start

1. Copy `.env.sample` to `.env` and fill in the values
2. `make install` (install dependencies)
3. `make run` (start the app on port 8000)
4. `make request` (send a test haiku request from a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DT_ENDPOINT` | Yes | | Dynatrace environment URL |
| `DT_API_TOKEN` | Yes | | Dynatrace API token |
| `OLLAMA_URL` | No | `http://localhost:11434/v1` | Ollama OpenAI-compatible endpoint |
| `MODEL` | No | `llama3.2` | Ollama model to use |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app on port 8000 with OTLP export to Dynatrace |
| `make request` | POST /haiku to localhost:8000 |
| `make help` | Show all available targets |

## Llama Stack configuration

`config.yaml` is a minimal distribution with the Responses API (Llama Stack's agent runtime, `inline::builtin`), its required file, vector and tool providers, and the `remote::ollama` inference provider. `POST /haiku` runs one Responses API turn with agent instructions. Models are discovered from Ollama at startup and addressed as `ollama/<model>`.
