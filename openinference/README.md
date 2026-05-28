# OpenInference + Dynatrace AI Observability

![OpenInference and Dynatrace](assets/openinference.png)

Generate a haiku with an LLM, send the OpenTelemetry trace to Dynatrace, and see it in the **AI Observability** app.
OpenInference uses its own semantic conventions (`llm.model_name`, `llm.token_count.*`, etc.) — this example shows two ways to normalize them into the Dynatrace `gen_ai.*` format.

---

## Table of contents

- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Configuration options](#configuration-options)
- [Setup](#setup)
  - [1. Create a Dynatrace access token](#1-create-a-dynatrace-access-token)
  - [2. Set environment variables](#2-set-environment-variables)
  - [3. Install dependencies](#3-install-dependencies)
- [Option A -- OTel Collector with transform processor](#option-a----otel-collector-with-transform-processor)
- [Option B -- Dynatrace OpenPipeline](#option-b----dynatrace-openpipeline)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [Troubleshooting](#troubleshooting)

---

## What you'll build

- Calls an LLM to generate a haiku using the OpenInference instrumentation library.
- Produces OpenTelemetry traces with OpenInference semantic conventions.
- Normalizes OpenInference attributes to Dynatrace `gen_ai.*` format -- either via a local OTel Collector or via Dynatrace OpenPipeline.
- Shows the trace in the Dynatrace AI Observability app with model, token usage, and message content.

---

## Prerequisites

- A Dynatrace tenant -- start a free trial at https://dt-url.net/trial
- Docker installed and running (Option A only)
- Python 3.8+
- An OpenAI-compatible API key and endpoint

---

## Configuration options

OpenInference uses its own semantic conventions that the Dynatrace AI Observability app does not natively understand. Two equivalent approaches normalize the attributes:

|  | Option A -- OTel Collector | Option B -- OpenPipeline |
|---|---|---|
| **Where transforms run** | In the collector process | Server-side, in your Dynatrace tenant |
| **Requires Docker** | Yes | No |
| **Requires Dynatrace config** | No | Yes -- one-time deploy |
| **Good for** | Full control over the pipeline, works anywhere you can run a collector | Simpler ops -- no collector to manage |
| **Make target** | `make run` | `make deploy-openpipeline` then `make run-openpipeline` |

Both paths produce identical results in the AI Observability app.

---

## Setup

### 1. Create a Dynatrace access token

1. In Dynatrace press `Ctrl+K` and search for **Access tokens**.
2. Create a token with these permissions:
   - `openTelemetryTrace.ingest`
   - `settings.read` and `settings.write` *(Option B only -- needed to deploy OpenPipeline)*
3. Copy the token value.

### 2. Set environment variables

The app and scripts read credentials from environment variables. The easiest way is to create a `.env` file in this directory (the Makefile sources it automatically):

```bash
# .env
DT_ENDPOINT=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.****.*****

OPENAI_API_KEY=**********************
OPENAI_API_BASE=https://your-endpoint.openai.azure.com/   # optional, for Azure or custom providers
MODEL=gpt-4o-mini                                         # optional, defaults to gpt-5-nano-2025-08-07
```

> **Note:** `DT_ENDPOINT` is your base tenant URL -- not the `/api/v2/otlp` path. Example: `https://abc12345.live.dynatrace.com`.

If you are not using the Makefile, export them directly in your shell:

```bash
export DT_ENDPOINT=https://abc12345.live.dynatrace.com
export DT_API_TOKEN=dt0c01.****.*****
export OPENAI_API_KEY=**********************
```

### 3. Install dependencies

```bash
# with make
make install

# or manually
pip install -r requirements.txt
```

---

## Option A -- OTel Collector with transform processor

The OTel Collector intercepts spans and applies all OpenInference -> `gen_ai.*` attribute mappings before forwarding to Dynatrace. No Dynatrace configuration needed.

```
App  ->  OTel Collector (transform processor)  ->  Dynatrace Grail
```

The collector needs your Dynatrace credentials because **it is the component that forwards spans to Dynatrace**. The app itself only knows about `http://localhost:4318` -- it sends spans to the collector, and the collector authenticates with Dynatrace using `DT_ENDPOINT` and `DT_API_TOKEN`.

### Step 1 -- Start the collector

```bash
# with make (reads .env automatically)
make run
```

Or manually with Docker:

```bash
docker run -d \
  --name otel-collector \
  -p 4318:4318 \
  -v $(pwd)/otel-collector-config.yaml:/collector-config.yaml:ro \
  -e DT_ENDPOINT=https://abc12345.live.dynatrace.com \
  -e DT_API_TOKEN=dt0c01.****.***** \
  otel/opentelemetry-collector-contrib:0.153.0 \
  --config=/collector-config.yaml
```

What happens:
- The collector listens on port `4318` for incoming OTLP/HTTP spans from the app.
- The `transform/openinference` processor renames `llm.model_name` -> `gen_ai.request.model`, maps token counts, operation kinds, and more.
- The processed spans are forwarded to `$DT_ENDPOINT/api/v2/otlp` authenticated with the API token.

### Step 2 -- Run the app

```bash
# with make (starts collector and app together)
make run

# or manually, once the collector is already running
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
OTEL_EXPORTER_OTLP_HEADERS="" \
python3 app.py
```

**Useful commands:**

```bash
make logs   # tail collector.log in real time
make stop   # stop and remove the collector container

# or manually
docker logs -f otel-collector
docker stop otel-collector && docker rm otel-collector
```

---

## Option B -- Dynatrace OpenPipeline

OpenPipeline is a server-side processing pipeline in Dynatrace that applies the same attribute mappings before spans are stored. The app sends spans directly to Dynatrace -- no collector needed.

```
App  ->  Dynatrace OpenPipeline (transform)  ->  Dynatrace Grail
```

### Step 1 -- Deploy the OpenPipeline configuration

This is a one-time setup per tenant. It deploys `openpipeline-openinference.yaml` and configures routing so OpenInference spans are automatically directed to the pipeline.

```bash
# with make (reads .env automatically)
make deploy-openpipeline

# or manually
DT_ENDPOINT=https://abc12345.live.dynatrace.com \
DT_API_TOKEN=dt0c01.****.***** \
bash deploy-openpipeline.sh
```

The script will:
1. Convert `openpipeline-openinference.yaml` to the Dynatrace Settings API format.
2. Validate the pipeline config against the tenant schema.
3. Create or update the `openinference-ai-spans` pipeline.
4. Add a routing entry so all spans with `otel.scope.name` matching `openinference` are routed to the pipeline.

To validate without making any changes:

```bash
bash deploy-openpipeline.sh --dry-run
```

### Step 2 -- Run the app

The app sends spans directly to `$DT_ENDPOINT/api/v2/otlp`, authenticated with the API token. OpenPipeline intercepts and transforms the spans server-side before they are stored.

```bash
# with make (reads .env automatically)
make run-openpipeline

# or manually
OTEL_EXPORTER_OTLP_ENDPOINT=https://abc12345.live.dynatrace.com/api/v2/otlp \
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token dt0c01.****.*****" \
python3 app.py
```

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears as a span with model name, token usage, and message content.
3. Open a span to inspect the full conversation and `gen_ai.*` attributes.

<!-- Screenshot: AI Observability overview showing OpenInference haiku spans -->

<!-- Screenshot: Span detail view showing gen_ai.request.model, gen_ai.usage.input_tokens, gen_ai.input.messages -->

---

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are correctly set.
- Confirm the token has `openTelemetryTrace.ingest` permission.
- Option A: check collector logs with `make logs` or `docker logs otel-collector`.
- Option B: run `python3 app.py` directly -- any auth error from Dynatrace will appear in the console output.

**Collector crashes on startup (Option A):**
- Run `docker ps -a` and `docker logs otel-collector` to see the error.
- Confirm Docker is running and port `4318` is free: `lsof -i :4318`.

**OpenPipeline deploy fails (Option B):**
- Confirm the token has `settings.read` and `settings.write` permissions.
- Run `bash deploy-openpipeline.sh --dry-run` to validate without writing.

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.system` or `gen_ai.provider.name` to be set on the span -- these are added by the transform processor / OpenPipeline.
- Option A: confirm the collector started with `otel-collector-config.yaml` -- check `docker logs otel-collector` for the config path it loaded.
- Option B: confirm the OpenPipeline routing entry is active -- go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `openinference-ai-spans` pipeline is enabled.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
