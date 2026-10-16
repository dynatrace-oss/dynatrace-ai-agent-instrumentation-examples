# Together AI + OpenInference + Dynatrace AI Observability

Generate a haiku with Together AI, send the OpenTelemetry trace to Dynatrace, and see it in the **AI Observability** app.
The app sets `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true`, so OpenInference emits OTel GenAI semantic-convention attributes (`gen_ai.*`) natively. No attribute normalization is needed; the collector or OpenPipeline only derives the `gen_ai.client.*` metrics.

---

## Table of contents

- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Configuration options](#configuration-options)
- [Setup](#setup)
- [Option A -- Bindplane collector](#option-a----bindplane-collector)
- [Option B -- Dynatrace OpenPipeline](#option-b----dynatrace-openpipeline)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [Metrics](#metrics)
- [Known gaps & limitations](#known-gaps--limitations)
- [Troubleshooting](#troubleshooting)

---

## What you'll build

- Calls Together AI to generate a haiku using the `openinference-instrumentation-together` instrumentation library.
- Produces OpenTelemetry traces with native `gen_ai.*` attributes (enabled by `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true` in [`app.py`](app.py)).
- Derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` from the spans, either in the Bindplane collector or in Dynatrace OpenPipeline.
- Shows the trace in the Dynatrace AI Observability app with model, token usage, and message content.

Together AI exposes an OpenAI-compatible chat completions API for open models (Llama, Qwen, DeepSeek, and more). `TogetherInstrumentor` wraps the native `together` Python SDK (v2+).

> `OPENINFERENCE_ENABLE_GENAI_SEMCONV` depends on OpenInference package behavior: it is implemented in `openinference-instrumentation` 0.1.71+, which `openinference-instrumentation-together` 0.1.12 requires. The OpenInference `llm.*` attributes are still emitted alongside `gen_ai.*`.

---

## Prerequisites
- A Dynatrace tenant -- start a free trial at https://dt-url.net/trial
- Docker installed and running (Option A only)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A [Together AI API key](https://api.together.ai/settings/api-keys)

---

## Configuration options

OpenInference is span-only, so the AI Observability metrics must be derived from spans. Two equivalent approaches do this:

|  | Option A -- Bindplane collector | Option B -- OpenPipeline |
|---|---|---|
| **Where metric derivation runs** | In the collector process, via the `span_metrics` and `signal_to_metrics` connectors | Server-side, in your Dynatrace tenant |
| **Requires Docker** | Yes | No |
| **Requires Dynatrace config** | No | Yes -- one-time deploy |
| **Good for** | Full control over the pipeline, works anywhere you can run a collector, no need to manually add pipeline configurations on your tenant | Simpler ops -- no collector to manage |
| **Make target** | `make run` | `make run-openpipeline` (deploy once first) |

> Why not the [Dynatrace Distribution of the OpenTelemetry Collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) for Option A? It does not ship a `signal_to_metrics`-equivalent connector, so the token-usage metric (`gen_ai.client.token.usage`) couldn't be derived. Option B has no such gap since the metric is extracted server-side.

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

TOGETHER_API_KEY=**********************
MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo   # optional, defaults to meta-llama/Llama-3.3-70B-Instruct-Turbo
```

> **Note:** `DT_ENDPOINT` is your base tenant URL -- not the `/api/v2/otlp` path. Example: `https://abc12345.live.dynatrace.com`.

If you are not using the Makefile, source the file directly in your shell:

```bash
source .env
```

### 3. Install dependencies

```bash
make install
```

---

## Option A -- Bindplane collector

The [Bindplane Distro for OpenTelemetry (BDOT)](https://github.com/observIQ/bindplane-otel-collector) collector forwards the spans to Dynatrace and derives the `gen_ai.client.*` metrics from them. No Dynatrace configuration needed.

```
App (native gen_ai.*)  ->  Bindplane collector (metrics)  ->  Dynatrace Grail
```

This example pins the collector to `ghcr.io/observiq/bindplane-agent:1.109.0`, matching the version pinned by the [`openai/openinference`](../../openai/openinference/) example. The pin means a future version bump surfaces regressions in the e2e test.

The collector needs your Dynatrace credentials because **it is the component that forwards spans to Dynatrace**. The app itself only knows about `http://localhost:4318` -- it sends spans to the collector, and the collector authenticates with Dynatrace using `DT_ENDPOINT` and `DT_API_TOKEN`.

### Step 1 -- Start the collector and run the app

```bash
# with make (reads .env automatically, starts the collector then runs app.py once)
make run
```

Or manually with Docker:

**Linux/macOS:**
```bash
source .env
docker run -d \
  --name bindplane-otel-collector \
  -p 4318:4318 \
  -v $(pwd)/otel-collector-config.yaml:/etc/otel/config.yaml:ro \
  -e DT_ENDPOINT=$DT_ENDPOINT \
  -e DT_API_TOKEN=$DT_API_TOKEN \
  ghcr.io/observiq/bindplane-agent:1.109.0
```

**Windows CMD:**
```cmd
set DT_ENDPOINT=https://abc12345.live.dynatrace.com
set DT_API_TOKEN=dt0c01.*****
docker run -d ^
  --name bindplane-otel-collector ^
  -p 4318:4318 ^
  -v %cd%/otel-collector-config.yaml:/etc/otel/config.yaml:ro ^
  -e DT_ENDPOINT=%DT_ENDPOINT% ^
  -e DT_API_TOKEN=%DT_API_TOKEN% ^
  ghcr.io/observiq/bindplane-agent:1.109.0
```

The BDOT image reads its config from `/etc/otel/config.yaml` by default in standalone mode, so no `--config` argument is needed.

What happens:
- The collector listens on port `4318` for incoming OTLP/HTTP spans from the app.
- A second pipeline branch keeps only LLM spans and feeds the metric connectors.
- Spans and derived metrics are forwarded to `$DT_ENDPOINT/api/v2/otlp` authenticated with the API token.

If you started the collector manually, run the app once against it:

```bash
source .env && OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 OTEL_EXPORTER_OTLP_HEADERS="" python3 app.py
```

**Useful commands:**

```bash
make logs   # tail collector.log in real time
make stop   # stop and remove the collector container

# or manually
docker logs -f bindplane-otel-collector
docker stop bindplane-otel-collector && docker rm bindplane-otel-collector
```

---

## Option B -- Dynatrace OpenPipeline

OpenPipeline is a server-side processing pipeline in Dynatrace. The app sends spans directly to Dynatrace -- no collector needed. The pipeline only derives the `gen_ai.client.*` metrics; the spans already carry `gen_ai.*`.

```
App (native gen_ai.*)  ->  Dynatrace OpenPipeline (metrics)  ->  Dynatrace Grail
```

### Step 1 -- Deploy the OpenPipeline configuration using the Dynatrace UI

This is a one-time setup per tenant.

1. In Dynatrace press `Ctrl+K` and search for **OpenPipeline**.
2. Select **Spans**.
3. Click **Add pipeline**, name it `together-openinference-ai-spans`, and add processors matching the definitions in [`openpipeline-openinference.yaml`](openpipeline-openinference.yaml).
4. Go to the **Routing** tab and add an entry:
    - Matcher: `isNotNull(openinference.span.kind) AND service.name == "together/openinference-openpipeline"`
    - Pipeline: `together-openinference-ai-spans`

> **Note:** OpenPipeline routing is first-match-wins, not fan-out. `isNotNull(openinference.span.kind)` alone (a span attribute set by every OpenInference instrumentor) would also match spans from any other OpenInference demo in this repo running on the same tenant -- e.g. `openai/openinference`'s `openinference-ai-spans` pipeline. Scoping the matcher with `service.name` (as above) keeps this demo's routing independent of whichever other OpenInference pipelines happen to be deployed.

### Step 2 -- Run the app

The app sends spans directly to `$DT_ENDPOINT/api/v2/otlp`, authenticated with the API token. OpenPipeline derives the metrics server-side.

```bash
# with make (reads .env automatically)
make run-openpipeline

# or manually
source .env && OTEL_EXPORTER_OTLP_ENDPOINT=$DT_ENDPOINT/api/v2/otlp OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $DT_API_TOKEN" python3 app.py
```

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer tab, with model, token usage, and cost for the `together/openinference` service.
3. Open a prompt trace to inspect the request/response content and the agents topology graph.

---

## Metrics

OpenInference is span-only by design (its instrumentors emit no metric instruments), so the two metrics the AI Observability app charts must be derived from the spans. Both options do this, so the cost and latency tiles populate either way:

| Metric | Option A (collector) | Option B (OpenPipeline) |
|---|---|---|
| `gen_ai.client.operation.duration` (s) | `span_metrics` connector, on LLM spans | `samplingAwareHistogramMetric` extractor on `duration_seconds` |
| `gen_ai.client.token.usage` (`gen_ai.token.type` = `input`/`output`) | `signal_to_metrics` connector, two sum defs | two `samplingAwareValueMetric` extractors, one per direction |

Both read the native `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`. Both metrics use delta temporality -- Dynatrace rejects cumulative.

---

## Known gaps & limitations

### No embeddings coverage

`TogetherInstrumentor` only wraps Together AI's `chat.completions` endpoint (not its embeddings, images, or audio endpoints) -- unlike [`openai/openinference`](../../openai/openinference/), whose `OpenAIInstrumentor` also covers the embeddings endpoint.

---

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are correctly set.
- Confirm the token has `openTelemetryTrace.ingest` permission.
- Option A: check collector logs with `make logs` or `docker logs bindplane-otel-collector`.
- Option B: run `python3 app.py` directly -- any auth error from Dynatrace will appear in the console output.

**Collector crashes on startup (Option A):**
- Run `docker ps -a` and `docker logs bindplane-otel-collector` to see the error.
- Confirm Docker is running and port `4318` is free: `lsof -i :4318`.

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.provider.name` (or `gen_ai.system`) on the span. With `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true`, OpenInference sets it from `llm.provider` (`together`).
- Check the console span output of `app.py`: `gen_ai.*` attributes should be present. If only `llm.*` attributes appear, the installed `openinference-instrumentation` is older than 0.1.71.
- Option B: confirm the OpenPipeline routing entry is active; go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `together-openinference-ai-spans` pipeline is enabled and the routing matcher is `isNotNull(openinference.span.kind) AND service.name == "together/openinference-openpipeline"`.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
