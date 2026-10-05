# LangGraph + OpenInference + Dynatrace AI Observability

Instrument a [LangGraph](https://langchain-ai.github.io/langgraph/) agent with OpenInference and send traces to Dynatrace AI Observability.
Uses [`openinference-instrumentation-langchain`](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-langchain) to auto-instrument LangGraph, and a [Bindplane OTel collector](https://github.com/observIQ/bindplane-agent) with the `genainormalizer` processor to translate OpenInference attributes to Dynatrace `gen_ai.*` format.

---

## Table of contents

- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Run the example](#run-the-example)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)

---

## What you'll build

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body).
- Builds a minimal LangGraph state graph with a single `write_haiku` node that calls Azure OpenAI.
- Produces OpenTelemetry traces with OpenInference semantic conventions.
- Routes traces through a local Bindplane collector that normalizes `llm.*` attributes to `gen_ai.*` before forwarding to Dynatrace.
- Shows the trace in the Dynatrace AI Observability app with model name, token usage, and message content.

---

## Prerequisites

- A Dynatrace tenant — start a free trial at https://dt-url.net/trial
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker (to run the Bindplane collector)
- An Azure OpenAI endpoint and key

---

## Setup

### 1. Create a Dynatrace access token

1. In Dynatrace press `Ctrl+K` and search for **Access tokens**.
2. Create a token with these permissions:
   - `openTelemetryTrace.ingest`
   - `metrics.ingest` (for the derived GenAI client metrics)
3. Copy the token value.

### 2. Set environment variables

Create a `.env` file in this directory (the Makefile sources it automatically):

```bash
# .env
DT_ENDPOINT=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.****.*****

AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=...
OPENAI_API_VERSION=2024-07-01-preview
MODEL=<deployment-name>
```

### 3. Install dependencies

```bash
make install
```

---

## Run the example

In one terminal, start the collector and server:

```bash
make run
```

In a second terminal, send a haiku request:

```bash
make request
```

The server runs on port 8000. `make run` starts a Bindplane collector on port 4318 first, then starts the FastAPI app pointing to it. Traces flow: app → collector (normalizes OpenInference → `gen_ai.*`) → Dynatrace.

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer tab as a span with model name, token usage, and message content.
3. Open a span to inspect the full `gen_ai.*` attributes including the LangGraph graph execution.

---

## How it works

`openinference-instrumentation-langchain` instruments LangChain/LangGraph via the callback system, producing spans with OpenInference semantic conventions (`llm.model_name`, `llm.token_count.*`, etc.). These are not natively understood by Dynatrace AI Observability, which expects `gen_ai.*` OTel semantic conventions.

The Bindplane collector's `genainormalizer` processor translates them:

| OpenInference attribute | `gen_ai.*` equivalent |
|---|---|
| `llm.model_name` | `gen_ai.request.model` |
| `llm.token_count.prompt` | `gen_ai.usage.input_tokens` |
| `llm.token_count.completion` | `gen_ai.usage.output_tokens` |
| `llm.input_messages.N.*` | `gen_ai.input.messages` (JSON array) |
| `llm.output_messages.N.*` | `gen_ai.output.messages` (JSON array) |

Two additional processors run after normalization:

- **`transform/response_model`** — mirrors `gen_ai.request.model` → `gen_ai.response.model` when absent (OpenInference has no separate response-model field).
- **`transform/output_prompt_results`** — extracts Azure OpenAI content-filter verdicts from the `output.value` JSON blob emitted by LangChain's Azure OpenAI integration and sets them as `gen_ai.prompt.prompt_filter_results`. This makes per-prompt filter results (hate, self-harm, sexual, violence, jailbreak) visible in Dynatrace AI Observability's content-filter view.

### Derived metrics

OpenInference is span-only: it emits no metric instruments, so the two GenAI client metrics the AI Observability app charts are derived from the normalized spans by collector connectors.

| Metric | Derived by |
|---|---|
| `gen_ai.client.operation.duration` (s) | `span_metrics` connector, on LLM spans |
| `gen_ai.client.token.usage` (`gen_ai.token.type` = `input`/`output`) | `signal_to_metrics` connector, two sum defs (one per direction) |

Both run on a separate `traces/genai_metrics` pipeline branch, so the `filter/genai_only` filter that restricts them to LLM spans can never drop a span from the trace export path. Both use delta temporality, which Dynatrace metric ingest requires (cumulative is dropped). The Dynatrace API token needs the `metrics.ingest` scope in addition to `openTelemetryTrace.ingest`.

---

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are set correctly.
- Check collector logs: `make logs` — any auth error from Dynatrace will appear there.

**Spans visible in Distributed Tracing but not AI Observability:**
- AI Observability requires `gen_ai.system` or `gen_ai.provider.name` on the span.
- Confirm the Bindplane collector is running: `docker ps | grep langgraph-openinference-otel-collector`.
- If the collector exited, check `make logs` for startup errors.

**`make stop` to clean up the collector container:**
```bash
make stop
```
