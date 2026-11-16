# Google ADK + OneAgent

This sample traces a [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) agent with Dynatrace using **OneAgent auto-instrumentation**, with no manual OpenTelemetry export or collector. OneAgent's Google ADK sensor captures the agent, LLM, and tool calls and ships `gen_ai.*` spans straight to Dynatrace.

For OpenTelemetry-based variants, see [`google-adk/opentelemetry`](../opentelemetry), [`google-adk/openinference`](../openinference), and [`google-adk/zero-code`](../zero-code).

## What this sample does

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body)
- Runs a single ADK `LlmAgent` on the Gemini API through ADK's `InMemoryRunner`
- Relies on OneAgent to capture the agent's LLM calls as `gen_ai.*` spans

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv`)
- Dynatrace OneAgent installed on the host (Linux)
- A Gemini API key

## Environment

Copy `.env.sample` to `.env` and fill in the values:

```env
GOOGLE_API_KEY=...
MODEL=gemini-3.1-flash-lite
```

## Install and run

```bash
cd google-adk/oneagent
make install
make run
```

Then in a second terminal:

```bash
make request
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Create venv and install dependencies via uv |
| `make run` | Start the FastAPI app on port 8000 |
| `make request` | POST /haiku with a sample topic |

## Dynatrace views

Open the **AI Observability** app and filter by `service.name = google-adk/oneagent` to explore the agentic trace, model, token usage, and latency.
