# OpenInference (Anthropic) + Dynatrace AI Observability

![AI Observability -- anthropic/openinference service explorer](assets/explorer.png)

Generate a haiku with Claude via the Anthropic Python SDK's `AnthropicBedrock` client, send the OpenTelemetry trace to Dynatrace, and see it in the **AI Observability** app.
This example enables `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true` in `app.py`, so OpenInference emits `gen_ai.*` attributes natively alongside its `llm.*` attributes. No downstream normalization is needed. The Bindplane collector or Dynatrace OpenPipeline still derives metrics from the spans.

This mirrors [`openai/openinference`](../../openai/openinference/), swapping the OpenAI SDK + `openinference-instrumentation-openai` for the Anthropic SDK + [`openinference-instrumentation-anthropic`](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-anthropic). It calls Claude through AWS Bedrock -- same as [`anthropic/oneagent`](../oneagent/) -- so it reuses the AWS credentials already configured for e2e CI instead of requiring a separate Anthropic API key.

**How this differs from `aws-bedrock/openinference`:** that example instruments at the `boto3`/`botocore` `invoke_model` level with `openinference-instrumentation-bedrock`, which is generic across every Bedrock-hosted model family. This example instruments at the Anthropic SDK level with `openinference-instrumentation-anthropic`, which understands the Messages API's request/response shape natively (message roles, content blocks, cache token breakdown) and produces richer, more precise `llm.*` attributes for Claude specifically -- at the cost of only working for Claude.

---

## Table of contents

- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Configuration options](#configuration-options)
- [Setup](#setup)
- [Option A -- Bindplane collector for metrics](#option-a----bindplane-collector-for-metrics)
- [Option B -- Dynatrace OpenPipeline](#option-b----dynatrace-openpipeline)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [Attribute mapping reference](#attribute-mapping-reference)
- [Metrics](#metrics)
- [Known gaps & limitations](#known-gaps--limitations)
- [Troubleshooting](#troubleshooting)

---

## What you'll build

- Calls Claude (via AWS Bedrock) to generate a haiku using the `anthropic` Python SDK's `AnthropicBedrock` client, instrumented with `openinference-instrumentation-anthropic`.
- Produces OpenTelemetry traces with native `gen_ai.*` semantic conventions, including the actual response model.
- Derives GenAI metrics from spans -- either via the Bindplane collector or via Dynatrace OpenPipeline.
- Shows the trace in the Dynatrace AI Observability app with model, token usage, and message content.

---

## Prerequisites

- A Dynatrace tenant -- start a free trial at https://dt-url.net/trial
- Docker installed and running (Option A only)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) with Anthropic model access enabled in Bedrock -- same requirement as [`anthropic/oneagent`](../oneagent/#prerequisites)

---

## Configuration options

OpenInference emits the `gen_ai.*` attributes used by AI Observability directly. Two equivalent approaches derive metrics without overwriting those attributes:

|  | Option A -- Bindplane collector | Option B -- OpenPipeline |
|---|---|---|
| **Where metrics are derived** | In the collector (`span_metrics` + `signal_to_metrics`) | Server-side, in your Dynatrace tenant |
| **Requires Docker** | Yes | No |
| **Requires Dynatrace config** | No | Yes -- one-time deploy (replace any older normalization pipeline -- see [Option B](#option-b----dynatrace-openpipeline)) |
| **Good for** | Full control over the pipeline, works anywhere you can run a collector, no need to manually add pipeline configurations on your tenant | Simpler ops -- no collector to manage |
| **Make target** | `make run` | `make run-openpipeline` (deploy once first) |

Both paths preserve the native `gen_ai.input.messages` / `gen_ai.output.messages` JSON, including multi-block responses, and surface the request in the AI Observability app.

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

AWS_ACCESS_KEY_ID=****************
AWS_SECRET_ACCESS_KEY=****************
AWS_DEFAULT_REGION=us-east-1                                 # optional, defaults to us-east-1
ANTHROPIC_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0   # optional, same default
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

## Option A -- Bindplane collector for metrics

The [Bindplane Distro for OpenTelemetry (BDOT)](https://github.com/observIQ/bindplane-otel-collector) collector forwards spans with their native `gen_ai.*` attributes and derives duration and token-usage metrics. No Dynatrace pipeline configuration is needed.

```
App  ->  Bindplane collector (metrics extraction)  ->  Dynatrace Grail
```

This example pins the collector to `ghcr.io/observiq/bindplane-agent:1.109.0`, which bundles the `span_metrics` and `signal_to_metrics` connectors.

The collector needs your Dynatrace credentials because **it is the component that forwards spans to Dynatrace**. The app itself only knows about `http://localhost:4318` -- it sends spans to the collector, and the collector authenticates with Dynatrace using `DT_ENDPOINT` and `DT_API_TOKEN`.

The pipeline removes duplicate raw `llm.*` attributes with `transform/cleanup_raw_attrs` and keeps only model-call spans on the metrics branch. It does not normalize or rebuild the native model/message attributes (see [`otel-collector-config.yaml`](otel-collector-config.yaml)).

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
  --name bindplane-otel-collector-anthropic \
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
  --name bindplane-otel-collector-anthropic ^
  -p 4318:4318 ^
  -v %cd%/otel-collector-config.yaml:/etc/otel/config.yaml:ro ^
  -e DT_ENDPOINT=%DT_ENDPOINT% ^
  -e DT_API_TOKEN=%DT_API_TOKEN% ^
  ghcr.io/observiq/bindplane-agent:1.109.0
```

The BDOT image reads its config from `/etc/otel/config.yaml` by default in standalone mode, so no `--config` argument is needed.

What happens:
- The collector listens on port `4318` for incoming OTLP/HTTP spans from the app.
- Native `gen_ai.*` attributes are preserved, and metrics are derived from model-call spans.
- The processed spans are forwarded to `$DT_ENDPOINT/api/v2/otlp` authenticated with the API token.

If you started the collector manually, run the app once against it:

```bash
source .env && OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 OTEL_EXPORTER_OTLP_HEADERS="" python3 app.py
```

**Useful commands:**

```bash
make logs   # tail collector.log in real time
make stop   # stop and remove the collector container

# or manually
docker logs -f bindplane-otel-collector-anthropic
docker stop bindplane-otel-collector-anthropic && docker rm bindplane-otel-collector-anthropic
```

---

## Option B -- Dynatrace OpenPipeline

OpenPipeline derives metrics server-side from the native `gen_ai.*` attributes before spans are stored. The app sends spans directly to Dynatrace -- no collector needed.

```
App  ->  Dynatrace OpenPipeline (metrics extraction)  ->  Dynatrace Grail
```

[`openpipeline-openinference.yaml`](openpipeline-openinference.yaml) derives metrics without remapping the native span attributes. If you previously deployed an OpenInference normalization pipeline, replace its processors with this configuration so the older model/message mappings do not overwrite native attributes. A metrics-only pipeline from the current `openai/openinference/` example can also handle these spans.

### Step 1 -- Deploy the OpenPipeline configuration using the Dynatrace UI
This is a one-time setup per tenant.

1. In Dynatrace press `Ctrl+K` and search for **OpenPipeline**.
2. Select **Spans**.
3. Click **Add pipeline**, name it `openinference-ai-spans`, and add processors matching the definitions in `openpipeline-openinference.yaml`.
4. Go to the **Routing** tab and add an entry:
    - Matcher: `isNotNull(openinference.span.kind)`
    - Pipeline: `openinference-ai-spans`

> **Note:** The routing matcher uses `isNotNull(openinference.span.kind)` (a span attribute set by every OpenInference instrumentor). Using `otel.scope.name` does not work — OpenPipeline routing evaluates span attributes only, not OTLP scope-level fields.

---

### Step 2 -- Run the app

The app sends spans directly to `$DT_ENDPOINT/api/v2/otlp`, authenticated with the API token. OpenPipeline derives metrics without remapping the span attributes.

```bash
# with make (reads .env automatically)
make run-openpipeline

# or manually
source .env && OTEL_EXPORTER_OTLP_ENDPOINT=$DT_ENDPOINT/api/v2/otlp OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $DT_API_TOKEN" python3 app.py
```

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer as the `anthropic/openinference` service, with model, token usage, and prompt trace populated -- no problems, no guardrail activations.
   ![AI Observability -- anthropic/openinference service explorer](assets/explorer.png)
3. Open the prompt trace to inspect the reconstructed conversation (`System prompt` / `Input`), trace metadata (model version, conversation ID), and the Agents Topology graph connecting the model, provider, and service.
   ![AI Observability -- anthropic/openinference prompt trace detail](assets/haiku-prompt-detail.png)

---

## Attribute mapping reference

With `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true`, the pinned instrumentation emits these attributes before either pipeline receives the span:

| Source | Native GenAI attribute |
|---|---|
| `llm.token_count.prompt` | `gen_ai.usage.input_tokens` |
| `llm.token_count.completion` | `gen_ai.usage.output_tokens` |
| `llm.token_count.prompt_details.cache_read` / `.cache_write` | `gen_ai.usage.cache_read.input_tokens` / `gen_ai.usage.cache_creation.input_tokens` |
| `llm.model_name` | `gen_ai.request.model` |
| `llm.provider` / `llm.system` (both always `"anthropic"`, set by the instrumentor) | `gen_ai.provider.name` |
| `session.id` | `gen_ai.conversation.id` |
| `openinference.span.kind` | `gen_ai.operation.name` (`LLM`→`chat`) |
| `llm.input_messages.N.*` / `llm.output_messages.N.*` | `gen_ai.input.messages` / `gen_ai.output.messages` (JSON with roles and content parts) |
| Response payload `model` (also emitted as `llm.response.model_name`) | `gen_ai.response.model` |
| Response payload `id` / `llm.finish_reason` | `gen_ai.response.id` / `gen_ai.response.finish_reasons` |
| `llm.invocation_parameters` | `gen_ai.request.*` parameters such as `max_tokens` |

The response model comes from the actual response, not a copy of the request model. Both pipeline options preserve it.

---

## Metrics

OpenInference is span-only by design (its instrumentors emit no metric instruments), so the two metrics the AI Observability app charts must be derived from the spans. Both options do this, so the cost and latency tiles populate either way:

| Metric | Option A (collector) | Option B (OpenPipeline) |
|---|---|---|
| `gen_ai.client.operation.duration` (s) | `span_metrics` connector, on LLM spans | `samplingAwareHistogramMetric` extractor on `duration_seconds` |
| `gen_ai.client.token.usage` (`gen_ai.token.type` = `input`/`output`) | `signaltometrics` connector, two sum defs | two `samplingAwareValueMetric` extractors, one per direction |

Both read the normalized `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` (mapped from OpenInference's `llm.token_count.*`, which for Anthropic already folds in cache-write and cache-read tokens -- see [`_get_token_counts`](https://github.com/Arize-ai/openinference/blob/main/python/instrumentation/openinference-instrumentation-anthropic/src/openinference/instrumentation/anthropic/_utils.py)). **Option A** derives both metrics in the Bindplane collector — `signaltometrics` (token) is bundled there alongside `genainormalizer`; requires the token's `metrics.ingest` scope, and both metrics use delta temporality (Dynatrace rejects cumulative). **Option B** derives the same two metrics server-side via the metric-extraction processors in [`openpipeline-openinference.yaml`](openpipeline-openinference.yaml); the token metric uses the two-extractor pattern (one per direction, both writing `gen_ai.client.token.usage` with a constant `gen_ai.token.type` dimension).

---

## Known gaps & limitations

### Request-model attribution in the pinned instrumentation

The native converter in `openinference-instrumentation==0.1.71` derives `gen_ai.request.model` from `llm.model_name`, which the Anthropic instrumentor updates from the response. It may therefore reflect the returned model rather than the requested Bedrock model ID. The requested model ID is retained in `llm.request.model_name` on the raw span and in `input.value`; `gen_ai.response.model` correctly reflects the response.

### Optional attributes

Native emission uses `gen_ai.usage.cache_read.input_tokens` and `gen_ai.usage.cache_creation.input_tokens` rather than the custom `gen_ai.prompt_caching` flag. The synthesized system message is included in `gen_ai.input.messages`; the pinned converter does not emit a separate `gen_ai.system_instructions` for this request.

### System prompt is synthesized as `llm.input_messages.0`

The Anthropic Messages API takes `system` as a separate top-level request parameter rather than a `{"role": "system", ...}` entry in `messages`. `openinference-instrumentation-anthropic` synthesizes a `role: "system"` message at index 0 so it still shows up in the reconstructed conversation -- this app.py's `system="You are a haiku poet."` string ends up as `llm.input_messages.0.message.content` exactly like an OpenAI system message would.

### No prompt-caching demo in this example

Anthropic prompt caching (`cache_control` blocks) requires a system/context block long enough to clear a per-model minimum cacheable token count -- 4,096 tokens for `claude-haiku-4-5` on Bedrock (see [`anthropic/oneagent`'s `style_guide.py`](../oneagent/style_guide.py) and its [prompt-caching notes](../oneagent/README.md#prompt-caching)). This example's one-line system prompt does not reach it. Extending `app.py` with a cacheable `system` block allows the native cache-token attributes to populate.

---

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are correctly set.
- Confirm the token has `openTelemetryTrace.ingest` permission.
- Option A: check collector logs with `make logs` or `docker logs bindplane-otel-collector-anthropic`.
- Option B: run `python3 app.py` directly -- any auth error from Dynatrace or AWS will appear in the console output.

**AWS auth or `AccessDeniedException` on startup:**
- Confirm `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are set and valid, and that the account has Anthropic model access enabled in Bedrock for the target region -- see [`anthropic/oneagent`'s prerequisites](../oneagent/README.md#prerequisites).

**Collector crashes on startup (Option A):**
- Run `docker ps -a` and `docker logs bindplane-otel-collector-anthropic` to see the error.
- Confirm Docker is running and port `4318` is free: `lsof -i :4318`.

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.provider.name` (or `gen_ai.system`) to be set on the span -- `genainormalizer` sets `gen_ai.provider.name` from `llm.provider`.
- Option A: confirm the `genainormalizer` processor ran -- the raw `llm.*` attributes should be gone and `gen_ai.*` attributes present in the collector debug output (`make logs`).
- Option B: confirm the OpenPipeline routing entry is active; go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `openinference-ai-spans` pipeline is enabled and the routing matcher is `isNotNull(openinference.span.kind)`.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
