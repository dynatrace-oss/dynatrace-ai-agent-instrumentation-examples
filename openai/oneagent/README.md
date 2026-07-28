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

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make help` | Show all available targets |

## Smartscape service entity

OneAgent uses the `FastAPI(title=...)` parameter to assign a Smartscape SERVICE entity. Apps with the same title on the same host are merged into one entity, which pollutes the topology. Each oneagent demo sets a unique title matching its service name so that each service gets its own distinct SERVICE (and GENAI_SERVICE) entity in Smartscape.

## Metrics via OpenPipeline

OneAgent captures the `gen_ai.*` span attributes above, but doesn't emit the `gen_ai.client.token.usage` / `gen_ai.client.operation.duration` metrics the AI Observability app's cost and latency dashboard tiles chart. A shared, tenant-side OpenPipeline pipeline derives both from these same span attributes — deployed once per tenant, not per demo. See [`openpipeline/openpipeline-oneagent-genai-metrics.yaml`](../../openpipeline/openpipeline-oneagent-genai-metrics.yaml) for the pipeline definition and deploy instructions.
