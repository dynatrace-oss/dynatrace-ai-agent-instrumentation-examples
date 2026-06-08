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
- [Known gaps & limitations](#known-gaps--limitations)
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

|  | Option A -- OTel Collector                                                                                                             | Option B -- OpenPipeline                                                                                    |
|---|----------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| **Where transforms run** | In the collector process                                                                                                               | Server-side, in your Dynatrace tenant                                                                       |
| **Requires Docker** | Yes                                                                                                                                    | No                                                                                                          |
| **Requires Dynatrace config** | No                                                                                                                                     | Yes -- one-time deploy                                                                                      |
| **Good for** | Full control over the pipeline, works anywhere you can run a collector, no need to manually add pipeline configurations on your tenant | Simpler ops -- no collector to manage|
| **Make target** | `make run`                                                                                                                             | `make run-openpipeline` (deploy once first)                                                                 |

Both paths produce identical results in the AI Observability app.

### Attribute mapping reference

The table below shows all OpenInference → Dynatrace translations applied by both options:

| OpenInference source | Dynatrace target | Notes |
|---|---|---|
| `openinference.span.kind` | `gen_ai.operation.kind` | `CHAIN`→`workflow`, `TOOL`→`tool`, `AGENT`→`agent`, `RETRIEVER`→`retrieval`, `GUARDRAIL`→`guardrail`, anything else→`task` |
| _(LLM span detected)_ | `gen_ai.operation.name = "chat"` | hardcoded when `llm.token_count.total` or `llm.model_name` present |
| _(embedding span detected)_ | `gen_ai.operation.name = "embeddings"` | hardcoded when `embedding.model_name` present |
| `llm.model_name` | `gen_ai.request.model` | LLM spans |
| `embedding.model_name` | `gen_ai.request.model` | embedding spans |
| `reranker.model_name` | `gen_ai.request.model` | reranker spans |
| _(derived)_ | `gen_ai.response.model` | mirrored from `gen_ai.request.model` (OpenInference has no separate response model field) |
| `llm.provider` | `gen_ai.provider.name` | primary mapping |
| `llm.system` | `gen_ai.provider.name` | fallback when `llm.provider` absent; `llm.system` is always removed afterwards |
| _(derived)_ | `gen_ai.system = "azure.ai.openai"` | set when `gen_ai.provider.name == "azure"` |
| `llm.token_count.prompt` | `gen_ai.usage.input_tokens` | |
| `llm.token_count.completion` | `gen_ai.usage.output_tokens` | |
| `llm.token_count.prompt_details.cache_read` | `gen_ai.prompt_caching = "read"` | source attribute removed |
| `llm.token_count.prompt_details.cache_write` | `gen_ai.prompt_caching = "write"` | only set when `cache_read` is absent; source attribute removed |
| `llm.temperature` | `gen_ai.request.temperature` | |
| `llm.max_tokens` | `gen_ai.request.max_tokens` | |
| `llm.top_p` | `gen_ai.request.top_p` | |
| `llm.finish_reason` | `gen_ai.response.finish_reasons` | string promoted to single-element array |
| `embedding.vector_length` | `gen_ai.embeddings.dimension.count` | |
| `agent.name` | `gen_ai.agent.name` | |
| `tool.name` | `gen_ai.tool.name` | |
| `tool.description` | `gen_ai.tool.description` | |
| `validator_name` | `gen_ai.guardrail.name` | `validator_name` has no OTel namespace; renamed for queryability |
| `llm.input_messages.0.message.content` | `gen_ai.system_instructions` | only when `llm.input_messages.0.message.role == "system"` |
| `input.value` | `gen_ai.input.messages` | interim fallback so spans appear in the Prompts list view; source removed |
| `output.value` | `gen_ai.output.messages` | interim fallback; source removed |
| _(hardcoded)_ | `ai.observability.source = "openinference"` | always set on all OpenInference spans |

### Attributes not translated

Some OpenInference attributes are intentionally left as-is:

| Attribute(s) | Why not translated |
|---|---|
| `llm.token_count.total` | No Dynatrace target field; used only as a guard condition to detect LLM spans. Kept for debugging. |
| `llm.finish_reason` | Source string retained alongside the translated `gen_ai.response.finish_reasons` array. Both coexist. |
| `openinference.span.kind` | Kept alongside the translated `gen_ai.operation.kind`; useful for pipeline routing and debugging. |
| `llm.input_messages.N.message.role/content` (N ≥ 1) | Indexed per-message attributes — OTTL and DQL cannot iterate over dynamic indices. Only index `0` is read for system instructions. The full conversation is surfaced via `input.value` → `gen_ai.input.messages`. |
| `llm.output_messages.N.message.role/content` | Same reason as above. |
| `session.id`, `user.id` | Names already match the OTel standard; pass through to Dynatrace unchanged. |

---

## Known gaps & limitations

These are OpenInference signals that are not yet fully captured after normalization:

### Full conversation message history

OpenInference emits each message as a separate indexed attribute (`llm.input_messages.0.message.role`, `llm.input_messages.1.message.role`, …). Neither OTTL (OTel Collector transform processor) nor Dynatrace OpenPipeline DQL can iterate over dynamic numeric indices at transform time.

**What we do instead:** the system prompt (`llm.input_messages.0.message.role == "system"`) is extracted to `gen_ai.system_instructions`, and the full serialised conversation is copied from `input.value` → `gen_ai.input.messages` as a fallback so spans appear in the Prompts view.

### Guardrail details beyond the validator name

`openinference.span.kind == "GUARDRAIL"` spans are now mapped to `gen_ai.operation.kind = "guardrail"` and `validator_name` is renamed to `gen_ai.guardrail.name`. However, richer guardrail attributes (blocked status, policy details, scores) have no standardised OTel target yet and are not translated.

The Dynatrace AI Observability app's guardrail dashboards currently read provider-specific attributes (`gen_ai.prompt.prompt_filter_results` for Azure, `gen_ai.bedrock.guardrail.*` for AWS Bedrock) rather than OpenInference guardrail spans. OpenInference guardrail spans will appear in Distributed Tracing but may not populate the guardrail overview tiles until a cross-provider mapping is standardised.

### EVALUATOR spans

`openinference.span.kind == "EVALUATOR"` spans fall through to the default `gen_ai.operation.kind = "task"`. No dedicated operation kind or attribute mapping exists yet.

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

OPENAI_API_KEY=**********************
OPENAI_API_BASE=https://your-endpoint.openai.azure.com/   
MODEL=gpt-4o-mini                                         # optional, defaults to gpt-4o
OPENAI_API_VERSION=2024-07-01-preview               # optional, required for Azure OpenAI endpoints
```

> **Note:** `DT_ENDPOINT` is your base tenant URL -- not the `/api/v2/otlp` path. Example: `https://abc12345.live.dynatrace.com`.

If you are not using the Makefile, source the file directly in your shell:

```bash
source .env
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

**Linux/macOS:**
```bash
source .env
docker run -d \
  --name otel-collector \
  -p 4318:4318 \
  -v $(pwd)/otel-collector-config.yaml:/etc/otelcol/otel-collector-config.yaml:ro \
  -e DT_ENDPOINT=$DT_ENDPOINT \
  -e DT_API_TOKEN=$DT_API_TOKEN \
  ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.48.0 \
  --config=/etc/otelcol/otel-collector-config.yaml
```

**Windows CMD:**
```cmd
set DT_ENDPOINT=https://abc12345.live.dynatrace.com
set DT_API_TOKEN=dt0c01.*****
docker run -d ^
  --name otel-collector ^
  -p 4318:4318 ^
  -v %cd%/otel-collector-config.yaml:/etc/otelcol/otel-collector-config.yaml:ro ^
  -e DT_ENDPOINT=%DT_ENDPOINT% ^
  -e DT_API_TOKEN=%DT_API_TOKEN% ^
  ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.48.0 ^
  --config=/etc/otelcol/otel-collector-config.yaml
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
source .env && OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 OTEL_EXPORTER_OTLP_HEADERS="" python3 app.py
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

### Step 1 -- Deploy the OpenPipeline configuration using the Dynatrace UI
This is a one-time setup per tenant.

1. In Dynatrace press `Ctrl+K` and search for **OpenPipeline**.
   ![Search for OpenPipeline](assets/searchOP.png)
2. Select **Spans**.
   ![Select Spans](assets/spans.png)
3. Click **Add pipeline**, name it `openinference-ai-spans`, and add processors matching the definitions in `openpipeline-openinference.yaml`.
   ![Add pipeline](assets/addpipeline.png)
4. Go to the **Routing** tab and add an entry:
    - Matcher: `matchesPhrase(otel.scope.name, "openinference")`
    - Pipeline: `openinference-ai-spans`

---

### Step 2 -- Run the app

The app sends spans directly to `$DT_ENDPOINT/api/v2/otlp`, authenticated with the API token. OpenPipeline intercepts and transforms the spans server-side before they are stored.

```bash
# with make (reads .env automatically)
make run-openpipeline

# or manually
source .env && OTEL_EXPORTER_OTLP_ENDPOINT=$DT_ENDPOINT/api/v2/otlp OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token $DT_API_TOKEN" python3 app.py
```

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer tab as a span with model name, token usage, and message content.
  ![AI Observability — span explorer](assets/explorer.png)
3. Open a span to inspect the full conversation and `gen_ai.*` attributes.
  ![AI Observability — haiku span detail](assets/haikuview.png)
4. You can also visualize span from the **Distributed Tracing** App
  ![AI Observability — OpenInference spans overview](assets/openinference.png)


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

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.system` or `gen_ai.provider.name` to be set on the span -- these are added by the transform processor / OpenPipeline.
- Option A: confirm the collector started with `otel-collector-config.yaml` -- check `docker logs otel-collector` for the config path it loaded.
- Option B: confirm the OpenPipeline routing entry is active -- go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `openinference-ai-spans` pipeline is enabled.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
