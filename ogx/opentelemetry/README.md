# OGX + OpenTelemetry Demo

Runs [OGX](https://github.com/ogx-ai/ogx) (formerly Llama Stack, the runtime behind the GenAI Playground and GenAI Studio in Red Hat OpenShift AI 3.x) in library mode inside a FastAPI app, with inference served by a local Ollama, and exports traces and metrics directly to Dynatrace over OTLP. The setup follows the [OGX telemetry guide](https://ogx-ai.github.io/docs/building_applications/telemetry): `opentelemetry-bootstrap` installs the instrumentations and `opentelemetry-instrument` wraps the process.

`POST /haiku` runs one turn of the OGX Responses API, its agent runtime. OGX's Ollama provider sends the model calls through the `openai` Python client, so `opentelemetry-instrumentation-openai-v2` produces the `gen_ai.*` chat spans. OGX itself emits `ogx.*` metrics and non-semconv tool spans (`invoke_tool`), but no GenAI agent spans, so `invoke_agent` spans and `gen_ai.agent.name` are not expected.

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

## OGX configuration

`config.yaml` is a minimal OGX distribution with the Responses API (`inline::builtin`), its required file, vector and tool providers, and the `remote::ollama` inference provider. Models are discovered from Ollama at startup and addressed as `ollama/<model>`.
