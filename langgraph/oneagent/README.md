# LangGraph + OneAgent

This sample traces a [LangGraph](https://langchain-ai.github.io/langgraph/) agent with Dynatrace using **OneAgent auto-instrumentation** — no manual OpenTelemetry export or collector. OneAgent instruments the underlying Azure OpenAI SDK calls and ships `gen_ai.*` spans straight to Dynatrace.

For a collector-based variant (which exports via OTLP and can redact secrets before they leave the host), see [`langgraph/opentelemetry/openai`](../opentelemetry/openai).

## What this sample does

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body)
- Builds a minimal LangGraph state graph with a single `write_haiku` node that calls Azure OpenAI
- Relies on OneAgent to capture the agent's LLM calls as `gen_ai.*` spans
- Relies on the OneAgent LangGraph sensor to add a workflow span for each graph run

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv`)
- Dynatrace OneAgent installed on the host
- An Azure OpenAI endpoint and key

## Enable the OneAgent GenAI features

In Dynatrace, go to **Settings** > **OneAgent features** and turn on both:

- The Python OpenAI GenAI feature (captures the chat completion spans)
- **Experimental Python GenAI LangGraph [Opt-In]** (requires OneAgent version 1.341 or later)

Restart the Python process after you change these settings; OneAgent reads them at process start.

With the LangGraph feature on, each `graph.invoke(...)` call produces a workflow span that wraps the LLM calls. It carries:

| Attribute | Value |
|-----------|-------|
| `gen_ai.operation.kind` | `workflow` |
| `gen_ai.agent.name` | The compiled graph's `name` |

Without it, you only see the OpenAI chat spans with no parent workflow span.

## Environment

Copy `.env.sample` to `.env` and fill in the values:

```env
OPENAI_API_BASE=https://<resource>.openai.azure.com/openai/deployments/<deployment>
OPENAI_API_KEY=...
OPENAI_API_VERSION=2024-07-01-preview
MODEL=<deployment>
```

> The app also accepts `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` as alternatives — both naming conventions are supported.

## Install and run

```bash
cd langgraph/oneagent
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
| `make build` / `make push` | Build / push the container image |

## Dynatrace views

Open the **AI Observability** app and filter by `service.name = langgraph/oneagent` to explore the agentic trace, model, token usage, and latency.
