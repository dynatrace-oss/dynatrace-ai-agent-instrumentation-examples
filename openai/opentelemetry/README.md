# OpenTelemetry (Traceloop SDK) + Dynatrace AI Observability

Generate a haiku with OpenAI, send the OpenTelemetry trace to Dynatrace, and see it in the **AI Observability** app.
Uses the [Traceloop SDK](https://github.com/traceloop/openllmetry) (OpenLLMetry), which auto-instruments the OpenAI SDK and emits `gen_ai.*` semantic conventions natively — no normalization layer needed.

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

- Calls an LLM to generate a haiku using the OpenAI SDK, auto-instrumented by the Traceloop SDK.
- Produces OpenTelemetry traces and metrics with `gen_ai.*` semantic conventions — no normalization step required.
- Exports directly to Dynatrace — no collector needed.
- Shows the trace in the Dynatrace AI Observability app with model name, token usage, and message content.

---

## Prerequisites

- A Dynatrace tenant — start a free trial at https://dt-url.net/trial
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- An OpenAI API key (or Azure OpenAI endpoint and key)

---

## Setup

### 1. Create a Dynatrace access token

1. In Dynatrace press `Ctrl+K` and search for **Access tokens**.
2. Create a token with these permissions:
   - `openTelemetryTrace.ingest`
   - `metrics.ingest`
3. Copy the token value.

### 2. Set environment variables

Create a `.env` file in this directory (the Makefile sources it automatically):

```bash
# .env
DT_ENDPOINT=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.****.*****

OPENAI_API_KEY=**********************
MODEL=gpt-4o-mini                            # optional, defaults to gpt-4o

# Azure OpenAI (optional)
OPENAI_API_BASE=https://your-resource.openai.azure.com/
OPENAI_API_VERSION=2024-07-01-preview
```

> **Note:** `DT_ENDPOINT` is your base tenant URL — not the `/api/v2/otlp` path. Example: `https://abc12345.live.dynatrace.com`.

### 3. Install dependencies

```bash
make install
```

---

## Run the example

```bash
make run
```

The app makes one streaming chat completion request, prints the haiku, and exits. Traces and metrics are exported directly to `$DT_ENDPOINT/api/v2/otlp`.

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer tab as a span with model name, token usage, and message content.
3. Open a span to inspect the full conversation and `gen_ai.*` attributes.

---

## How it works

The Traceloop SDK wraps the OpenAI Python SDK via `opentelemetry-instrumentation-openai`. With `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` it emits spans with `gen_ai.*` semantic conventions directly — unlike the [OpenInference example](../openinference/), no collector-side normalization is needed.

Key environment variables set by `app.py` before initializing the SDK:

| Variable | Value | Purpose |
|---|---|---|
| `TRACELOOP_TELEMETRY` | `false` | Disables Traceloop's PostHog usage telemetry |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | `delta` | Dynatrace ingests delta metrics only |
| `OTEL_SERVICE_NAME` | `openai` | Service name shown in Dynatrace |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `gen_ai_latest_experimental` | Enables `gen_ai.*` attribute emission |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | `true` | Captures prompt and response text as span attributes |

---

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are set correctly.
- Confirm the token has `openTelemetryTrace.ingest` and `metrics.ingest` permissions.
- Any auth error from Dynatrace will print to stdout.

**Spans visible in Distributed Tracing but not AI Observability:**
- AI Observability requires `gen_ai.system` or `gen_ai.provider.name` on the span.
- Confirm `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` is active — `app.py` sets this before importing Traceloop, so it should always be present.
