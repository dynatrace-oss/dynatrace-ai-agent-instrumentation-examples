# OpenInference (Node.js) + Dynatrace AI Observability

A small TypeScript HTTP service generates a haiku with the OpenAI Node.js SDK. [`@arizeai/openinference-instrumentation-openai`](https://www.npmjs.com/package/@arizeai/openinference-instrumentation-openai) traces each call. An OpenTelemetry Collector maps the spans to `gen_ai.*` attributes and derives metrics, then sends both to Dynatrace for the **AI Observability** app.

Unlike the Python instrumentors, OpenInference for JavaScript has no switch to emit `gen_ai.*` attributes natively. It emits `llm.*` / `openinference.*` attributes only, so the collector does the mapping.

---

## Table of contents

- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Run](#run)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [Attribute mapping](#attribute-mapping)
- [Metrics](#metrics)
- [Troubleshooting](#troubleshooting)

---

## What you'll build

- A Node.js server on port `8000` with a `POST /haiku` endpoint that takes `{"topic": "<value>"}`.
- OpenInference instrumentation that traces every OpenAI chat completion.
- A local collector that maps `llm.*` attributes to `gen_ai.*`, then derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage`.

```text
App (OpenInference llm.* spans) -> Bindplane collector (gen_ai.* mapping + metrics) -> Dynatrace
```

---

## Prerequisites

- A Dynatrace tenant (start a free trial at https://dt-url.net/trial)
- Docker installed and running
- Node.js 20 or later
- An OpenAI API key, or an Azure OpenAI or other OpenAI-compatible endpoint

---

## Setup

### 1. Create a Dynatrace access token

1. In Dynatrace, press `Ctrl+K` and search for **Access tokens**.
2. Create a token with these permissions:
   - `openTelemetryTrace.ingest`
   - `metrics.ingest`
3. Copy the token value.

### 2. Set environment variables

Copy `.env.sample` to `.env` in this directory and fill it in. The Makefile loads it automatically.

```bash
# .env
DT_ENDPOINT=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.****.*****

OPENAI_API_KEY=**********************
OPENAI_API_BASE=                       # optional, for Azure OpenAI or OpenAI-compatible endpoints
MODEL=gpt-4o-mini                      # optional, defaults to gpt-4o
OPENAI_API_VERSION=2024-07-01-preview  # optional, required for Azure OpenAI endpoints
```

> **Note:** `DT_ENDPOINT` is the base tenant URL (for example `https://abc12345.live.dynatrace.com`), not `/api/v2/otlp`.

### 3. Install dependencies

```bash
make install
```

---

## Run

Start the collector and the server:

```bash
make run
```

In a second terminal, send a request:

```bash
make request
```

Other targets:

```bash
make logs   # tail collector logs
make stop   # stop the collector
make help   # list all targets
```

If port `4318` is already in use, run the collector on another host port with `make run OTLP_PORT=4320`.

To run the app in a container instead, build it with `make build APP_IMAGE=<image>` and push it with `make push APP_IMAGE=<image>`.

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace, press `Ctrl+K` and search for **AI Observability**.
2. Find the `openai/openinference/node` service in Explorer.
3. Open the span to inspect the `gen_ai.*` attributes and messages.

---

## Attribute mapping

The `transform/genai` and `transform/messages` processors in [`otel-collector-config.yaml`](otel-collector-config.yaml) set these attributes:

| `gen_ai.*` attribute | Source |
|---|---|
| `gen_ai.operation.name` | `chat` when `openinference.span.kind` is `LLM` |
| `gen_ai.provider.name` | `llm.provider` (or `llm.system`) |
| `gen_ai.request.model` | `model` in `input.value` |
| `gen_ai.response.model` | `llm.model_name` |
| `gen_ai.request.temperature`, `gen_ai.request.max_tokens` | `input.value` |
| `gen_ai.response.id`, `gen_ai.response.finish_reasons` | `output.value` |
| `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` | `llm.token_count.prompt` / `llm.token_count.completion` |
| `gen_ai.system_instructions` | leading system message in `llm.input_messages` |
| `gen_ai.input.messages` / `gen_ai.output.messages` | `llm.input_messages` / `llm.output_messages` |

The message mapping covers this demo's shape: an optional system message, one user turn, and one assistant reply. After mapping, `transform/remove_legacy` drops the `llm.*` and `openinference.*` attributes.

---

## Metrics

OpenInference does not emit metrics. The collector derives the two metrics AI Observability needs from the spans:

- `gen_ai.client.operation.duration`
- `gen_ai.client.token.usage` (dimension `gen_ai.token.type` = `input` / `output`)

---

## Troubleshooting

**No spans in Dynatrace:**
- Check `DT_ENDPOINT` and `DT_API_TOKEN`.
- Check that the token has `openTelemetryTrace.ingest` and `metrics.ingest`.
- Check the collector logs (`make logs`).

**No OpenAI spans, only an empty trace:**
- The instrumentation must load before the `openai` module. `npm start` does this with `node --require ./dist/instrumentation.js`. Keep that flag if you change the start command.

**Spans in Distributed Tracing but not in AI Observability:**
- Check that `gen_ai.request.model` and `gen_ai.provider.name` are on the span.
