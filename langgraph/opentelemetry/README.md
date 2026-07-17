# LangGraph + Dynatrace

This sample instruments a [LangGraph](https://langchain-ai.github.io/langgraph/) agent with Dynatrace using [OpenLLMetry](https://github.com/traceloop/openllmetry) (Traceloop SDK). No separate OpenTelemetry collector required.

## What this sample does

- Runs a FastAPI server exposing `POST /haiku`
- Builds a minimal LangGraph state graph with a single `write_haiku` node that calls Azure OpenAI
- Exports traces and metrics directly to Dynatrace via OTLP HTTP

The Traceloop SDK auto-instruments LangChain and LangGraph, so each request produces a distributed trace covering the graph run and the underlying LLM call, with token usage and cost captured as metrics.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv`)
- A Dynatrace API token with `openTelemetryTrace.ingest` and `metrics.ingest`
- An Azure OpenAI endpoint and key

## Environment

Copy `.env.sample` to `.env` and fill in the values:

```env
DT_ENDPOINT=https://<tenant>.live.dynatrace.com
DT_API_TOKEN=dt0c01....

AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_KEY=...
OPENAI_API_VERSION=2024-07-01-preview
MODEL=<deployment>
```

## Install and run

```bash
cd langgraph/opentelemetry
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
| `make request` | POST /haiku to localhost:8000 |

## Dynatrace views

After a few minutes, refresh the Dynatrace views and you should see data being populated.

Explore how your graph runs, which models are used, and how token usage is attributed across nodes and LLM calls.

Remember that you can drill down into the end-to-end trace whenever a `trace.id` is shown. Just right-click the trace ID and "open with" `Distributed Tracing`.

You can also open the Dynatrace `Distributed Tracing` view and filter for `service.name = langgraph`.

In the Dynatrace **AI Observability** app you can filter by service or model to explore token usage, cost breakdown, and latency across your graph runs.

| View | What to look for |
|------|-----------------|
| **Distributed Tracing** | Filter by `service.name = langgraph` |
| **AI Observability** | Token usage, latency, and model per request |
