# Ollama + OpenInference Demo

Demonstrates tracing local Ollama chat calls with Dynatrace via OpenInference instrumentation (`OllamaInstrumentor`).
OpenInference uses its own semantic conventions (`llm.model_name`, `llm.token_count.*`, etc.) — this example shows two ways to normalize them into the Dynatrace `gen_ai.*` format: the Bindplane collector's `gen_ai_normalizer` processor, or Dynatrace OpenPipeline.

Ollama itself runs locally (or on any host you point `OLLAMA_HOST` at) — there is no cloud API key involved, unlike the other provider examples in this repo. See [`ollama/oneagent`](../oneagent/) for the OneAgent-instrumented equivalent of this same app.

---

## Table of contents

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

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker installed and running (Option A only)
- [Ollama](https://ollama.com/download) installed and running locally, with a model pulled:
  ```bash
  ollama pull llama3.2
  ```
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

> Why not the [Dynatrace Distribution of the OpenTelemetry Collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) for Option A? Its manifest does include `genainormalizerprocessor`, but it does not ship a `signal_to_metrics`-equivalent connector, so the token-usage metric (`gen_ai.client.token.usage`) couldn't be derived — the same gap that led `openai/openinference`, `cohere/openinference`, and `anthropic/openinference` to pin the Bindplane collector instead. Option B has no such gap since the metric is extracted server-side.

Both paths surface the request in the AI Observability app.

---

## Setup

### 1. Create a Dynatrace access token

1. In Dynatrace press `Ctrl+K` and search for **Access tokens**.
2. Create a token with these permissions:
   - `openTelemetryTrace.ingest`
3. Copy the token value.

### 2. Start Ollama and pull a model

```bash
ollama serve &
ollama pull llama3.2
```

The Ollama server listens on `http://localhost:11434` by default -- set `OLLAMA_HOST` if yours runs elsewhere.

### 3. Set environment variables

The app and scripts read credentials from environment variables. The easiest way is to create a `.env` file in this directory (the Makefile sources it automatically):

```bash
# .env
DT_ENDPOINT=https://abc12345.live.dynatrace.com
DT_API_TOKEN=dt0c01.****.*****

OLLAMA_HOST=http://localhost:11434          # optional, this is the default
MODEL=llama3.2                              # optional, defaults to llama3.2
```

> **Note:** `DT_ENDPOINT` is your base tenant URL -- not the `/api/v2/otlp` path. Example: `https://abc12345.live.dynatrace.com`.

### 4. Install dependencies

```bash
make install
```

---

## Option A -- Bindplane collector with gen_ai_normalizer

The [Bindplane Distro for OpenTelemetry (BDOT)](https://github.com/observIQ/bindplane-otel-collector) collector intercepts spans and normalizes OpenInference attributes to `gen_ai.*` with its built-in `gen_ai_normalizer` processor before forwarding to Dynatrace. No Dynatrace configuration needed.

```
App  ->  Bindplane collector (transform + gen_ai_normalizer)  ->  Dynatrace Grail
```

This example pins the collector to `ghcr.io/observiq/bindplane-agent:1.107.0`. The pin means a future version bump surfaces normalization changes in the e2e test.

The app knows only about `http://localhost:4318` -- it sends spans to the collector, and the collector authenticates with Dynatrace using `DT_ENDPOINT` and `DT_API_TOKEN`.

The pipeline runs three processors (see [`otel-collector-config.yaml`](otel-collector-config.yaml)):

1. **`transform/pre_normalize`** extracts `temperature`/`num_predict`/`top_p` from the `options` object nested inside `llm.invocation_parameters` before the normalizer deletes that attribute -- see [Attribute mapping reference](#attribute-mapping-reference) for why Ollama needs this extra nesting level.
2. **`gen_ai_normalizer`** (source `openinference`, `remove_originals: true`) maps the remaining OpenInference attributes to `gen_ai.*` -- including `llm.provider` (always `ollama`) to `gen_ai.provider.name`. `remove_originals` drops the raw `llm.*` attributes so exported spans carry only `gen_ai.*` fields.
3. **`transform/response_model`** mirrors `gen_ai.request.model` to `gen_ai.response.model`, which the AI Observability app requires and OpenInference has no separate field for.

### Run it

```bash
# with make (reads .env automatically, starts the collector then runs the app)
make run
```

Then, in a second terminal:

```bash
make request
```

**Useful commands:**

```bash
make logs   # tail collector.log in real time
make stop   # stop and remove the collector container
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
3. Click **Add pipeline**, name it `ollama-openinference-ai-spans`, and add processors matching the definitions in [`openpipeline-openinference.yaml`](openpipeline-openinference.yaml).
4. Go to the **Routing** tab and add an entry:
    - Matcher: `isNotNull(openinference.span.kind) AND service.name == "ollama/openinference-openpipeline"`
    - Pipeline: `ollama-openinference-ai-spans`

> **Note:** OpenPipeline routing is first-match-wins, not fan-out. `isNotNull(openinference.span.kind)` alone (a span attribute set by every OpenInference instrumentor) would also match spans from any other OpenInference demo in this repo running on the same tenant -- e.g. `cohere/openinference`'s `cohere-openinference-ai-spans` pipeline. Scoping the matcher with `service.name` (as above) keeps this demo's routing independent of whichever other OpenInference pipelines happen to be deployed.

### Step 2 -- Run the app

```bash
# with make (reads .env automatically)
make run-openpipeline

# or manually — leave OTEL_EXPORTER_OTLP_ENDPOINT unset; main.py's _otlp_exporter()
# then builds the authenticated $DT_ENDPOINT/api/v2/otlp request itself from
# DT_ENDPOINT/DT_API_TOKEN (setting it would route the app down the collector,
# no-auth branch of _otlp_exporter() instead)
source .env && uv run python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Then, in a second terminal:

```bash
make request
```

---

## Visualize in Dynatrace AI Observability

1. In Dynatrace press `Ctrl+K` and search for **AI Observability**.
2. Your haiku request appears in the Explorer tab, with model, token usage, and duration for the `ollama/openinference` service.
3. Open a prompt trace to inspect the request/response content and the agents topology graph.

> Screenshots pending -- no Dynatrace tenant browser session was available when this example was written. See the CI run for this PR for a live, working pipeline.

---

## Attribute mapping reference

Both options apply the same translations; the collector's `gen_ai_normalizer` (source `openinference`) reconstructs the full conversation from indexed per-message attributes, while OpenPipeline uses an interim fallback (see [Known gaps & limitations](#known-gaps--limitations)).

| OpenInference source | Dynatrace target |
|---|---|
| `llm.token_count.prompt` | `gen_ai.usage.input_tokens` |
| `llm.token_count.completion` | `gen_ai.usage.output_tokens` |
| `llm.model_name` | `gen_ai.request.model` |
| `llm.provider` (always `ollama`) | `gen_ai.provider.name` |
| `llm.finish_reason` (from the response's `done_reason`) | `gen_ai.response.finish_reasons` |
| `session.id` | `gen_ai.conversation.id` |
| `openinference.span.kind` | `gen_ai.operation.name` (`LLM`→`chat`, `TOOL`→`execute_tool`, `AGENT`/`CHAIN`→`invoke_agent`, `RETRIEVER`→`retrieval`) |
| `llm.input_messages.N.*` / `llm.output_messages.N.*` | `gen_ai.input.messages` / `gen_ai.output.messages` |
| `llm.invocation_parameters` (JSON: `options.temperature`, `options.num_predict`, `options.top_p`) | `gen_ai.request.temperature` / `gen_ai.request.max_tokens` / `gen_ai.request.top_p` |
| _(both options)_ | `gen_ai.response.model` (mirrored from `gen_ai.request.model`) |

`session.id` and `user.id` already match the OTel standard and pass through unchanged in both options.

> **Note on request parameters:** the `ollama` Python client takes `temperature`/`num_predict`/`top_p` as keys of a single `options={...}` dict passed to `chat()`, not as flat keyword arguments like the other provider SDKs in this repo. `OllamaInstrumentor` captures every `chat()` keyword argument other than `messages`/`model`/`tools` verbatim into `llm.invocation_parameters`, so `options` shows up as a nested JSON object one level deeper than e.g. `cohere/openinference`'s flat `{"temperature": ..., "max_tokens": ...}`. Both options' request-params processors account for this extra nesting level. Ollama has no `max_tokens` option; `num_predict` (the number of tokens to predict) is its equivalent, mapped to the standard `gen_ai.request.max_tokens`. This demo's `main.py` passes `temperature` and `num_predict` on every request; `top_p` is not passed and stays unset.

---

## Metrics

OpenInference is span-only by design (its instrumentors emit no metric instruments), so the two metrics the AI Observability app charts must be derived from the spans. Both options do this, so the cost and latency tiles populate either way:

| Metric | Option A (collector) | Option B (OpenPipeline) |
|---|---|---|
| `gen_ai.client.operation.duration` (s) | `span_metrics` connector, on LLM spans | `samplingAwareHistogramMetric` extractor on `duration_seconds` |
| `gen_ai.client.token.usage` (`gen_ai.token.type` = `input`/`output`) | `signal_to_metrics` connector, two sum defs | two `samplingAwareValueMetric` extractors, one per direction |

Both read the normalized `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` (mapped from OpenInference's `llm.token_count.*`, in turn taken from Ollama's own `prompt_eval_count`/`eval_count` response fields). Both metrics use delta temporality -- Dynatrace rejects cumulative.

---

## Known gaps & limitations

### Not instrumented

`OllamaInstrumentor` wraps only `ollama.chat` / `Client.chat` / `AsyncClient.chat`. Calls to `generate`, `embed`, or `embeddings` produce no spans -- there is no equivalent of the embedding processors present in `openai/openinference`'s pipeline to drop here, because Ollama's own client methods for those calls are simply untraced.

### Attributes gen_ai_normalizer does not map without help (Option A)

The `gen_ai_normalizer` `openinference` source does not parse `llm.invocation_parameters` at all -- both `gen_ai.request.temperature`, `gen_ai.request.max_tokens`, and `gen_ai.request.top_p` need the extra `transform/pre_normalize` step in [`otel-collector-config.yaml`](otel-collector-config.yaml) (see the note under [Attribute mapping reference](#attribute-mapping-reference)). Option B (OpenPipeline) already maps these server-side via its own `openinference-request-params` DQL processor.

Prompt caching (`gen_ai.prompt_caching` / `gen_ai.cache.type`) is not applicable here -- Ollama's chat API has no prompt-caching concept.

### Full conversation message history (Option B)

Option A reconstructs the full message history via `gen_ai_normalizer`. Option B (OpenPipeline) cannot: DQL cannot iterate over the indexed per-message attributes (`llm.input_messages.0.message.role`, `llm.input_messages.1.message.role`, …) at transform time, so it copies the serialized conversation from `input.value` → `gen_ai.input.messages` as a fallback.

---

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are correctly set.
- Confirm the token has `openTelemetryTrace.ingest` permission.
- Confirm Ollama is reachable at `OLLAMA_HOST` and the model in `MODEL` has been pulled (`ollama list`).
- Option A: check collector logs with `make logs` or `docker logs bindplane-otel-collector-ollama`.
- Option B: run the app directly -- any auth error from Dynatrace will appear in the console output.

**Collector crashes on startup (Option A):**
- Run `docker ps -a` and `docker logs bindplane-otel-collector-ollama` to see the error.
- Confirm Docker is running and port `4318` is free: `lsof -i :4318`.

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.provider.name` (or `gen_ai.system`) to be set on the span.
- Option A: confirm the `gen_ai_normalizer` processor ran -- the raw `llm.*` attributes should be gone and `gen_ai.*` attributes present in the collector debug output (`make logs`).
- Option B: confirm the OpenPipeline routing entry is active; go to **Settings -> OpenPipeline -> Spans** in Dynatrace and verify the `ollama-openinference-ai-spans` pipeline is enabled and the routing matcher is scoped to `service.name == "ollama/openinference-openpipeline"`.

**Port conflict (Option A):**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.

**`ollama.ResponseError: model not found` or connection refused:**
- Run `ollama pull $MODEL` (default `llama3.2`) and confirm `ollama serve` is running and reachable at `OLLAMA_HOST`.
