# Haystack + OpenInference Demo

Demonstrates tracing a [Haystack](https://haystack.deepset.ai/) pipeline (Azure OpenAI backend) with Dynatrace via OpenInference instrumentation (`HaystackInstrumentor`).
OpenInference uses its own semantic conventions (`llm.model_name`, `llm.token_count.*`, etc.) — this example shows two ways to normalize them into the Dynatrace `gen_ai.*` format: the Bindplane collector's `gen_ai_normalizer` processor, or Dynatrace OpenPipeline.

---

## Table of contents

- [What you'll build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Configuration options](#configuration-options)
- [Setup](#setup)
- [Option A -- Bindplane collector with gen_ai_normalizer](#option-a----bindplane-collector-with-gen_ai_normalizer)
- [Option B -- Dynatrace OpenPipeline](#option-b----dynatrace-openpipeline)
- [Visualize in Dynatrace AI Observability](#visualize-in-dynatrace-ai-observability)
- [Attribute mapping reference](#attribute-mapping-reference)
- [Metrics](#metrics)
- [Known gaps & limitations](#known-gaps--limitations)
- [Troubleshooting](#troubleshooting)

---

## What you'll build

- A two-component Haystack `Pipeline` (`ChatPromptBuilder` -> `AzureOpenAIChatGenerator`) that writes a haiku.
- `HaystackInstrumentor` wraps `Pipeline.run` and every component's `run` method directly, producing an OpenInference-shaped trace: one `CHAIN` span for the pipeline and one `LLM` span for the chat generator call.
- Normalizes those OpenInference attributes to Dynatrace `gen_ai.*` format -- either via the Bindplane collector's `gen_ai_normalizer` processor or via Dynatrace OpenPipeline.
- Shows the trace in the Dynatrace AI Observability app with model, token usage, and message content.

Haystack is also demoed via OneAgent auto-instrumentation in [`haystack/oneagent/`](../oneagent/) -- that example instruments the underlying `openai` SDK calls Haystack makes; this one instruments the Haystack pipeline/component layer itself.

---

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker installed and running (Option A only)
- An Azure OpenAI resource (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`)
- Dynatrace tenant with an API token scoped to `openTelemetryTrace.ingest`

---

## Configuration options

OpenInference uses its own semantic conventions that the Dynatrace AI Observability app does not natively understand. Two equivalent approaches normalize the attributes:

|  | Option A -- Bindplane collector | Option B -- OpenPipeline |
|---|---|---|
| **Where normalization runs** | In the collector process, via the `gen_ai_normalizer` processor | Server-side, in your Dynatrace tenant |
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

## Option A -- Bindplane collector with gen_ai_normalizer

The [Bindplane Distro for OpenTelemetry (BDOT)](https://github.com/observIQ/bindplane-otel-collector) collector intercepts spans and normalizes OpenInference attributes to `gen_ai.*` with its built-in `gen_ai_normalizer` processor before forwarding to Dynatrace. No Dynatrace configuration needed.

```
App  ->  Bindplane collector (gen_ai_normalizer + transform)  ->  Dynatrace Grail
```

This example pins the collector to `ghcr.io/observiq/bindplane-agent:1.107.0`. The pin means a future version bump surfaces normalization changes in the e2e test.

The app knows only about `http://localhost:4318` -- it sends spans to the collector, and the collector authenticates with Dynatrace using `DT_ENDPOINT` and `DT_API_TOKEN`.

The pipeline runs two processors (see [`otel-collector-config.yaml`](otel-collector-config.yaml)):

1. **`gen_ai_normalizer`** (source `openinference`, `remove_originals: true`) maps OpenInference attributes to `gen_ai.*`. `remove_originals` drops the raw `llm.*` attributes so exported spans carry only `gen_ai.*` fields.
2. **`transform/response_model`** mirrors `gen_ai.request.model` to `gen_ai.response.model`, which the AI Observability app requires and OpenInference has no separate field for.

### Run it

```bash
# with make (reads .env automatically, starts the collector then runs app.py once)
make run
```

**Useful commands:**

```bash
make logs   # tail collector.log in real time
make stop   # stop and remove the collector container
make request  # re-run the pipeline once against a collector already running
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
2. Select **Spans**.
3. Click **Add pipeline**, name it `haystack-openinference-ai-spans`, and add processors matching the definitions in [`openpipeline-openinference.yaml`](openpipeline-openinference.yaml).
4. Go to the **Routing** tab and add an entry:
    - Matcher: `isNotNull(openinference.span.kind) AND service.name == "haystack/openinference-openpipeline"`
    - Pipeline: `haystack-openinference-ai-spans`

> **Note:** OpenPipeline routing is first-match-wins, not fan-out. `isNotNull(openinference.span.kind)` alone (a span attribute set by every OpenInference instrumentor) would also match spans from any other OpenInference demo in this repo running on the same tenant -- e.g. `cohere/openinference`'s pipeline. Scoping the matcher with `service.name` (as above) keeps this demo's routing independent of whichever other OpenInference pipelines happen to be deployed on the tenant.

### Step 2 -- Run the app

```bash
# with make (reads .env automatically)
make run-openpipeline
```

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer tab, with model, token usage, and cost for the `haystack/openinference` service.
3. Open a prompt trace to inspect the request/response content.

> **Note:** Screenshots for this example are pending a live run against a real Dynatrace tenant and Azure OpenAI resource -- see [`assets/`](assets/). Contributions welcome; follow the naming pattern used in [`openai/openinference/assets/`](../../openai/openinference/assets/) (descriptive kebab-case filenames).

---

## Attribute mapping reference

Both options apply the same translations; the collector's `gen_ai_normalizer` (source `openinference`) reconstructs the full conversation from indexed per-message attributes, while OpenPipeline uses an interim fallback (see [Known gaps & limitations](#known-gaps--limitations)).

| OpenInference source | Dynatrace target |
|---|---|
| `llm.token_count.prompt` | `gen_ai.usage.input_tokens` |
| `llm.token_count.completion` | `gen_ai.usage.output_tokens` |
| `llm.model_name` | `gen_ai.request.model` |
| `llm.provider` (`AzureOpenAIChatGenerator` -> `azure`) | `gen_ai.provider.name` |
| `llm.system` (inferred from the model name) | `gen_ai.provider.name` (fallback, if `llm.provider` is absent) |
| `session.id` | `gen_ai.conversation.id` |
| `openinference.span.kind` | `gen_ai.operation.name` (`LLM` with `llm.model_name` set -> `chat`) / `gen_ai.operation.kind` (`CHAIN` -> `workflow`, else -> `task`) |
| `llm.input_messages.N.*` / `llm.output_messages.N.*` | `gen_ai.input.messages` / `gen_ai.output.messages` |
| _(both options)_ | `gen_ai.response.model` (mirrored from `gen_ai.request.model`) |

`session.id` and `user.id` already match the OTel standard and pass through unchanged in both options.

> **Note on the `ChatPromptBuilder` span:** `HaystackInstrumentor` tags the `ChatPromptBuilder` component's span as `openinference.span.kind == "LLM"` too (it only sets `llm.prompt_template.*`, never `llm.model_name` / `llm.token_count.*`). Both options key their LLM-call logic off `isNotNull(llm.token_count.total) OR isNotNull(llm.model_name)` rather than span kind, so the prompt-builder span is correctly excluded from the `chat` operation mapping.

> **Note on request parameters:** unlike the Cohere/Groq/Mistral OpenInference examples in this repo, `HaystackInstrumentor` never emits `llm.invocation_parameters` for a chat generator's span (only for its embedder spans, which this demo does not exercise) — there is no `gen_ai.request.temperature` / `top_p` / `max_tokens` source to map here at all.

---

## Metrics

OpenInference is span-only by design (its instrumentors emit no metric instruments), so the two metrics the AI Observability app charts must be derived from the spans. Both options do this, so the cost and latency tiles populate either way:

| Metric | Option A (collector) | Option B (OpenPipeline) |
|---|---|---|
| `gen_ai.client.operation.duration` (s) | `span_metrics` connector, on LLM spans | `samplingAwareHistogramMetric` extractor on `duration_seconds` |
| `gen_ai.client.token.usage` (`gen_ai.token.type` = `input`/`output`) | `signal_to_metrics` connector, two sum defs | two `samplingAwareValueMetric` extractors, one per direction |

Both read the normalized `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` (mapped from OpenInference's `llm.token_count.*`). Both metrics use delta temporality -- Dynatrace rejects cumulative.

---

## Known gaps & limitations

### Attributes gen_ai_normalizer does not yet map (Option A)

The `gen_ai_normalizer` `openinference` source does not set the following attributes. They are optional for the AI Observability app, and are candidates for upstream contribution to the processor:

- `gen_ai.response.finish_reasons` -- moot here anyway, since `HaystackInstrumentor` never captures a finish-reason span attribute in the first place (see [Attribute mapping reference](#attribute-mapping-reference)).

Request parameters (`gen_ai.request.temperature` / `top_p` / `max_tokens`) and prompt caching (`gen_ai.prompt_caching` / `gen_ai.cache.type`) are not applicable here -- `HaystackInstrumentor` does not capture either for chat generator spans.

### Full conversation message history (Option B)

Option A reconstructs the full message history via `gen_ai_normalizer`. Option B (OpenPipeline) cannot: DQL cannot iterate over the indexed per-message attributes (`llm.input_messages.0.message.role`, `llm.input_messages.1.message.role`, …) at transform time, so it copies the serialized conversation from `input.value` → `gen_ai.input.messages` as a fallback.

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
- Option A: confirm the `gen_ai_normalizer` processor ran -- the raw `llm.*` attributes should be gone and `gen_ai.*` attributes present in the collector debug output (`make logs`).
- Option B: confirm the OpenPipeline routing entry is active; go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `haystack-openinference-ai-spans` pipeline is enabled and the routing matcher is `isNotNull(openinference.span.kind) AND service.name == "haystack/openinference-openpipeline"`.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
