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
- [dtctl](https://github.com/dynatrace/dtctl) (Option B.1 only)

---

## Configuration options

OpenInference uses its own semantic conventions that the Dynatrace AI Observability app does not natively understand. Two equivalent approaches normalize the attributes:

|  | Option A -- OTel Collector | Option B -- OpenPipeline |
|---|---|---|
| **Where transforms run** | In the collector process | Server-side, in your Dynatrace tenant |
| **Requires Docker** | Yes | No |
| **Requires Dynatrace config** | No | Yes -- one-time deploy |
| **Good for** | Full control over the pipeline, works anywhere you can run a collector | Simpler ops -- no collector to manage |
| **Make target** | `make run` | `make run-openpipeline` (deploy once first) |

Both paths produce identical results in the AI Observability app.

### Attribute mapping reference

The table below shows which `gen_ai.*` attributes are produced after normalization:

| Attribute | Collector | OpenPipeline | Source |
|---|---|---|---|
| `gen_ai.operation.name` | ✅ | ✅ | hardcoded `chat` for LLM spans |
| `gen_ai.operation.kind` | ✅ | ✅ | mapped from `openinference.span.kind` |
| `gen_ai.request.model` | ✅ | ✅ | renamed from `llm.model_name` |
| `gen_ai.response.model` | ✅ | ✅ | mirrored from `gen_ai.request.model` |
| `gen_ai.provider.name` | ✅ | ✅ | renamed from `llm.provider` (fallback: `llm.system`) |
| `gen_ai.system` | ✅ | ✅ | set to `azure.ai.openai` when provider is `azure` |
| `gen_ai.usage.input_tokens` | ✅ | ✅ | renamed from `llm.token_count.prompt` |
| `gen_ai.usage.output_tokens` | ✅ | ✅ | renamed from `llm.token_count.completion` |
| `gen_ai.usage.prompt_caching.read_tokens` | ✅ | ✅ | renamed from `llm.token_count.prompt_details.cache_read` |
| `gen_ai.response.finish_reasons` | ✅ | ✅ | converted from `llm.finish_reason` string → array |
| `gen_ai.input.messages` | ✅ | ✅ | copied from `input.value` (interim fallback) |
| `gen_ai.output.messages` | ✅ | ✅ | copied from `output.value` (interim fallback) |
| `ai.observability.source` | ✅ | ✅ | hardcoded `openinference` |

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

### Step 1 -- Deploy the OpenPipeline configuration

This is a one-time setup per tenant.

---

#### Option B.1 -- Using dtctl

[dtctl](https://github.com/dynatrace/dtctl) uses the Dynatrace Platform API and requires a **platform OAuth token** (not a classic API token).

**Create a platform OAuth token (one-time):**

1. Go to [accounts.dynatrace.com](https://accounts.dynatrace.com) → **Identity & access management → OAuth clients**
2. Click **Create client**, give it a name, and add scopes: `settings:read`, `settings:write`
3. Save — copy the **Client ID** and **Client Secret**
4. Generate an access token:

```bash
curl -X POST https://sso.dynatrace.com/sso/oauth2/token \
  -d "grant_type=client_credentials&client_id=<CLIENT_ID>&client_secret=<CLIENT_SECRET>&scope=settings:read settings:write"
```

5. Copy the `access_token` from the response (valid for ~1 hour)

**Configure dtctl and deploy:**

```bash
source .env
DTCTL_ENV=$(echo $DT_ENDPOINT | sed 's|https://\([^.]*\)\.\(.*\)|https://\1.apps.\2|')
dtctl config set-credentials my-token --token <access_token>
dtctl ctx set my-tenant --environment $DTCTL_ENV --token-ref my-token
dtctl apply -f openpipeline-openinference-dtctl.yaml
```

Then add the routing entry safely (GET → merge → PUT, all via dtctl):

```bash
dtctl get settings --schema builtin:openpipeline.spans.routing --scope environment -o json \
  | python3 -c "
import json, sys
routing = json.load(sys.stdin)
entry = {
  'enabled': True,
  'pipelineType': 'custom',
  'customPipelineId': 'openinference-ai-spans',
  'matcher': 'matchesPhrase(otel.scope.name, \"openinference\")',
  'description': 'Route OpenInference spans to openinference-ai-spans pipeline'
}
for obj in routing:
    entries = obj.get('value', {}).get('routingEntries', [])
    entries = [e for e in entries if e.get('description') != entry['description']]
    entries.append(entry)
    obj['value']['routingEntries'] = entries
print(json.dumps(routing))
" | dtctl apply -f -
```

---

#### Option B.2 -- Using the Dynatrace AI Assistant

You can ask the Dynatrace AI assistant to create the pipeline for you.

1. In Dynatrace press `Ctrl+K` and open **Davis AI** or the AI chat.
2. Paste the following prompt:

```
Create an OpenPipeline pipeline for Spans named "openinference-ai-spans" that normalizes OpenInference (Arize Phoenix) semantic conventions to Dynatrace gen_ai.* format.

Add these processors:
1. DQL processor (matcher: true) — set gen_ai.operation.kind from openinference.span.kind: CHAIN→workflow, TOOL→tool, AGENT→agent, RETRIEVER→retrieval, default→task
2. fieldsAdd (matcher: isNotNull(llm.token_count.total) OR isNotNull(llm.model_name)) — set gen_ai.operation.name = "chat"
3. fieldsRename (same matcher) — llm.model_name→gen_ai.request.model, llm.provider→gen_ai.provider.name
4. fieldsRename (matcher: isNotNull(llm.system) AND isNull(gen_ai.provider.name)) — llm.system→gen_ai.provider.name
5. fieldsRename (same as 3) — llm.token_count.prompt→gen_ai.usage.input_tokens, llm.token_count.completion→gen_ai.usage.output_tokens
6. fieldsRename (matcher: cache tokens present) — llm.token_count.prompt_details.cache_read→gen_ai.usage.prompt_caching.read_tokens
7. fieldsRename (matcher: true) — llm.temperature→gen_ai.request.temperature, llm.max_tokens→gen_ai.request.max_tokens, llm.top_p→gen_ai.request.top_p
8. DQL (same as 3) — gen_ai.response.finish_reasons=array(llm.finish_reason), gen_ai.response.model=gen_ai.request.model, gen_ai.system="azure.ai.openai" when provider is azure
9. fieldsAdd (matcher: isNotNull(embedding.model_name)) — gen_ai.operation.name="embeddings"
10. fieldsRename (same) — embedding.model_name→gen_ai.request.model, embedding.vector_length→gen_ai.embeddings.dimension.count
11. fieldsRename (matcher: isNotNull(reranker.model_name)) — reranker.model_name→gen_ai.request.model
12. fieldsRename (true) — agent.name→gen_ai.agent.name
13. fieldsRename (isNotNull(tool.name)) — tool.name→gen_ai.tool.name, tool.description→gen_ai.tool.description
14. fieldsAdd (true) — ai.observability.source="openinference"
15. DQL (matcher: isNotNull(input.value) AND isNull(gen_ai.input.messages)) — gen_ai.input.messages=input.value, gen_ai.output.messages=output.value

Then add a routing entry: matcher matchesPhrase(otel.scope.name, "openinference") → this pipeline.
```

---

#### Option B.3 -- Using the Dynatrace UI

1. In Dynatrace press `Ctrl+K` and search for **OpenPipeline**.
2. Select **Spans** and click **Add pipeline**.
3. Name it `openinference-ai-spans` and add processors matching the definitions in `openpipeline-openinference.yaml`.
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

**OpenPipeline not transforming spans (Option B):**
- Confirm the token has `settings.read` and `settings.write` permissions.
- Re-run `bash deploy-openpipeline.sh` and `bash setup-routing.sh` to ensure the pipeline and routing are applied.

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.system` or `gen_ai.provider.name` to be set on the span -- these are added by the transform processor / OpenPipeline.
- Option A: confirm the collector started with `otel-collector-config.yaml` -- check `docker logs otel-collector` for the config path it loaded.
- Option B: confirm the OpenPipeline routing entry is active -- go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `openinference-ai-spans` pipeline is enabled.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
