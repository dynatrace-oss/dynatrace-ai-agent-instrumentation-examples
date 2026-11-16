# Cohere + OpenInference Demo

Demonstrates tracing Cohere v2 chat API calls with Dynatrace via OpenInference instrumentation (`CohereInstrumentor`).
This example enables `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true`, so OpenInference emits `gen_ai.*` attributes directly on spans (alongside `llm.*` / `openinference.*`). No attribute normalization is required. The collector only derives metrics.

---

## Table of contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Run with the Bindplane collector](#run-with-the-bindplane-collector)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [Attribute mapping reference](#attribute-mapping-reference)
- [Metrics](#metrics)
- [Known gaps & limitations](#known-gaps--limitations)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker installed and running
- A Cohere API key (`COHERE_API_KEY`)
- Dynatrace tenant with an API token scoped to `openTelemetryTrace.ingest`

---

## Setup

### 1. Create a Dynatrace access token

1. In Dynatrace press `Ctrl+K` and search for **Access tokens**.
2. Create a token with these permissions:
   - `openTelemetryTrace.ingest`
3. Copy the token value.

### 2. Set environment variables

Create a `.env` file in this directory:

```bash
DT_ENDPOINT=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.****.*****

COHERE_API_KEY=**********************
MODEL=command-r-08-2024
```

### 3. Install dependencies

```bash
make install
```

---

## Run with the Bindplane collector

Collector mode keeps spans untouched and derives only metrics.

```text
App (native gen_ai.* spans) -> Bindplane collector (metrics derivation) -> Dynatrace
```

Run:

```bash
make run
```

Then trigger a request:

```bash
make request
```

Useful commands:

```bash
make logs
make stop
```

---

## Visualize in Dynatrace AI Observability

1. Open **AI Observability** in Dynatrace.
2. Find service `cohere/openinference`.
3. Open a prompt trace to inspect input/output, model, and token usage.

---

## Attribute mapping reference

No mapping table is needed now: `CohereInstrumentor` emits `gen_ai.*` natively when `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true` is set (in `main.py`), including model/provider/usage/message attributes used by AI Observability.

---

## Metrics

OpenInference still emits no metric instruments, so the collector derives:

- `gen_ai.client.operation.duration` (seconds)
- `gen_ai.client.token.usage` (`gen_ai.token.type` = `input` / `output`)

Both rely on native `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` on spans.

---

## Known gaps & limitations

### `OPENINFERENCE_ENABLE_GENAI_SEMCONV` depends on OpenInference package behavior

This demo relies on OpenInference core behavior used by `openinference-instrumentation-cohere`. If upstream behavior changes, the collector config may need revisiting.

### Prompt caching attributes

Prompt caching attributes (`gen_ai.prompt_caching` / `gen_ai.cache.type`) are not expected here for standard Cohere chat usage.

---

## Troubleshooting

**No spans in Dynatrace**
- Verify `DT_ENDPOINT` and `DT_API_TOKEN`.
- Verify token scope `openTelemetryTrace.ingest`.

**Collector issues**
- Check logs: `make logs`
- Confirm Docker is running and `4318` is free.

**Spans in Distributed Tracing but not AI Observability**
- Confirm spans include `gen_ai.provider.name` and `gen_ai.request.model`.
