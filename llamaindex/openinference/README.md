# LlamaIndex + OpenInference Demo

Demonstrates tracing a [LlamaIndex](https://www.llamaindex.ai/) LLM call (Azure OpenAI backend) with Dynatrace via OpenInference instrumentation ([`LlamaIndexInstrumentor`](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-llama-index)).
The app sets `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true`, so OpenInference emits OTel GenAI `gen_ai.*` attributes natively; no attribute normalization is needed. OpenInference emits no metrics, so this example shows two ways to derive `gen_ai.client.*` metrics from the spans: a Bindplane collector, or Dynatrace OpenPipeline.

---

## Table of contents

- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Configuration options](#configuration-options)
- [Setup](#setup)
- [Option A -- Bindplane collector](#option-a----bindplane-collector)
- [Option B -- Dynatrace OpenPipeline](#option-b----dynatrace-openpipeline)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [Native gen_ai attributes](#native-gen_ai-attributes)
- [Metrics](#metrics)
- [Troubleshooting](#troubleshooting)

---

## What you'll build

- A LlamaIndex `AzureOpenAI` chat call that writes a haiku.
- `LlamaIndexInstrumentor` hooks the LlamaIndex instrumentation dispatcher and produces an OpenInference-shaped `LLM` span for the chat call.
- With `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true` (set in `app.py`), the span carries `gen_ai.*` attributes natively.
- Derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` from the spans, either via the Bindplane collector or via Dynatrace OpenPipeline.
- Shows the trace in the Dynatrace AI Observability app with model, token usage, and message content.

---

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker installed and running (Option A only)
- An Azure OpenAI resource (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`)
- Dynatrace tenant with an API token scoped to `openTelemetryTrace.ingest`

---

## Configuration options

Spans already carry `gen_ai.*` attributes. OpenInference emits no metrics, so two equivalent approaches derive them:

|  | Option A -- Bindplane collector | Option B -- OpenPipeline |
|---|---|---|
| **Where metric derivation runs** | In the collector process, via the `span_metrics` / `signal_to_metrics` connectors | Server-side, in your Dynatrace tenant |
| **Requires Docker** | Yes | No |
| **Requires Dynatrace config** | No | Yes -- one-time deploy |
| **Make target** | `make run` | `make run-openpipeline` (deploy once first) |

Both paths surface the request in the AI Observability app.

---

## Setup

### 1. Create a Dynatrace access token

1. In Dynatrace press `Ctrl+K` and search for **Access tokens**.
2. Create a token with these permissions:
   - `openTelemetryTrace.ingest`
3. Copy the token value.

### 2. Set environment variables

The app and scripts read credentials from environment variables. The easiest way is to create a `.env` file in this directory (the Makefile sources it automatically):

```bash
# .env
DT_ENDPOINT=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.****.*****

AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=**********************
AZURE_OPENAI_DEPLOYMENT=genai-demo                  # optional, defaults to genai-demo
OPENAI_API_VERSION=2024-07-01-preview               # optional, defaults to 2024-07-01-preview
```

> **Note:** `DT_ENDPOINT` is your base tenant URL -- not the `/api/v2/otlp` path. Example: `https://abc12345.live.dynatrace.com`.

### 3. Install dependencies

```bash
make install
```

---

## Option A -- Bindplane collector

The [Bindplane Distro for OpenTelemetry (BDOT)](https://github.com/observIQ/bindplane-otel-collector) collector forwards spans unchanged to Dynatrace and derives `gen_ai.client.*` metrics from them. No Dynatrace configuration needed.

```
App  ->  Bindplane collector (metric derivation)  ->  Dynatrace Grail
```

This example pins the collector to `ghcr.io/observiq/bindplane-agent:1.109.0`. The pin means a future version bump surfaces regressions in the e2e test.

The app knows only about `http://localhost:4318` -- it sends spans to the collector, and the collector authenticates with Dynatrace using `DT_ENDPOINT` and `DT_API_TOKEN`.

See [`otel-collector-config.yaml`](otel-collector-config.yaml): the traces pipeline exports spans as-is, and a second branch keeps only LLM spans and feeds the metric connectors (see [Metrics](#metrics)).

### Run it

```bash
# with make (reads .env automatically, starts the collector then runs app.py once)
make run
```

**Useful commands:**

```bash
make logs   # tail collector.log in real time
make stop   # stop and remove the collector container
make request  # re-run the app once against a collector already running
```

---

## Option B -- Dynatrace OpenPipeline

OpenPipeline is a server-side processing pipeline in Dynatrace. Here it only derives the `gen_ai.client.*` metrics from the spans. The app sends spans directly to Dynatrace -- no collector needed.

```
App  ->  Dynatrace OpenPipeline (metric extraction)  ->  Dynatrace Grail
```

### Step 1 -- Deploy the OpenPipeline configuration using the Dynatrace UI

This is a one-time setup per tenant.

1. In Dynatrace press `Ctrl+K` and search for **OpenPipeline**.
2. Select **Spans**.
3. Click **Add pipeline**, name it `llamaindex-openinference-ai-spans`, and add processors matching the definitions in [`openpipeline-openinference.yaml`](openpipeline-openinference.yaml).
4. Go to the **Routing** tab and add an entry:
    - Matcher: `isNotNull(openinference.span.kind) AND service.name == "llamaindex/openinference-openpipeline"`
    - Pipeline: `llamaindex-openinference-ai-spans`

> **Note:** OpenPipeline routing is first-match-wins, not fan-out. `isNotNull(openinference.span.kind)` alone (a span attribute set by every OpenInference instrumentor) would also match spans from any other OpenInference demo in this repo running on the same tenant -- e.g. `cohere/openinference`'s pipeline. Scoping the matcher with `service.name` (as above) keeps this demo's routing independent of whichever other OpenInference pipelines happen to be deployed on the tenant.

### Step 2 -- Run the app

```bash
# with make (reads .env automatically)
make run-openpipeline
```

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer tab, with model, token usage, and cost for the `llamaindex/openinference` service.
3. Open a prompt trace to inspect the request/response content and the agents topology graph.

---

## Native gen_ai attributes

`OPENINFERENCE_ENABLE_GENAI_SEMCONV=true` makes the OpenInference tracer add OTel GenAI attributes (for example `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.input.messages`, `gen_ai.output.messages`) alongside its own `llm.*` attributes when each span ends. Neither option renames or maps attributes. The exact set of `gen_ai.*` attributes depends on the installed `openinference-instrumentation` package version.

---

## Metrics

OpenInference is span-only by design (its instrumentors emit no metric instruments), so the two metrics the AI Observability app charts must be derived from the spans. Both options do this, so the cost and latency tiles populate either way:

| Metric | Option A (collector) | Option B (OpenPipeline) |
|---|---|---|
| `gen_ai.client.operation.duration` (s) | `span_metrics` connector, on LLM spans | `samplingAwareHistogramMetric` extractor on `duration_seconds` |
| `gen_ai.client.token.usage` (`gen_ai.token.type` = `input`/`output`) | `signal_to_metrics` connector, two sum defs | two `samplingAwareValueMetric` extractors, one per direction |

Both read the native `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` span attributes. Both metrics use delta temporality -- Dynatrace rejects cumulative.

---

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are correctly set.
- Confirm the token has `openTelemetryTrace.ingest` permission.
- Option A: check collector logs with `make logs` or `docker logs bindplane-otel-collector`.
- Option B: run `uv run python3 app.py` directly -- any auth error from Dynatrace will appear in the console output.

**Collector crashes on startup (Option A):**
- Run `docker ps -a` and `docker logs bindplane-otel-collector` to see the error.
- Confirm Docker is running and port `4318` is free: `lsof -i :4318`.

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.provider.name` (or `gen_ai.system`) to be set on the span.
- Confirm the span carries `gen_ai.*` attributes. If only `llm.*` attributes are present, check that `OPENINFERENCE_ENABLE_GENAI_SEMCONV` is not overridden to `false` in your environment and that `openinference-instrumentation` is recent enough to support it.

**No `gen_ai.client.*` metrics (Option B):**
- Confirm the OpenPipeline routing entry is active; go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `llamaindex-openinference-ai-spans` pipeline is enabled and the routing matcher is `isNotNull(openinference.span.kind) AND service.name == "llamaindex/openinference-openpipeline"`.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
