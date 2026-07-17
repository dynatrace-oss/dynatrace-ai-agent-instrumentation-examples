# LangGraph + Dynatrace

This sample instruments a [LangGraph](https://langchain-ai.github.io/langgraph/) agent with Dynatrace using [OpenLLMetry](https://github.com/traceloop/openllmetry) (Traceloop SDK), routed through a [Dynatrace OpenTelemetry Collector](https://github.com/Dynatrace/dynatrace-otel-collector) that anonymizes sensitive input messages.

## What this sample does

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body)
- Builds a minimal LangGraph state graph with a single `write_haiku` node that calls Azure OpenAI
- Exports traces and metrics via OTLP HTTP to a local Dynatrace Collector, which forwards them to Dynatrace

The Traceloop SDK auto-instruments LangChain and LangGraph, so each request produces a distributed trace covering the graph run and the underlying LLM call, with token usage and cost captured as metrics.

### Secret anonymization in the collector

The collector runs a `transform` processor (see `otel-collector-config.yaml`). Message content is captured per the GenAI semantic conventions as the `gen_ai.input.messages` / `gen_ai.output.messages` / `gen_ai.system_instructions` span attributes (this is opt-in — the app sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`). Any of these that mentions `secret` (case-insensitive) has its value replaced with `***REDACTED***` before the span leaves the collector, so the sensitive text never reaches Dynatrace. Values that do not match pass through unchanged.

For example, `POST /haiku {"topic": "the secret launch codes"}` is redacted, while `POST /haiku {"topic": "cherry blossoms in spring"}` is stored as-is.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv`)
- Docker (to run the Dynatrace Collector)
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
