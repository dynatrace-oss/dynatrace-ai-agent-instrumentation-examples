# Cohere + OpenInference Demo

Demonstrates tracing Cohere v2 chat API calls with Dynatrace via OpenInference instrumentation (`CohereInstrumentor`). The app exports spans over OTLP to a local Bindplane collector, which normalizes them and forwards them to Dynatrace.

## How it works

OpenInference uses its own semantic conventions (`llm.model_name`, `llm.token_count.*`, etc.) that the Dynatrace AI Observability app does not natively understand. This example normalizes them to the Dynatrace `gen_ai.*` format in the collector, so no Dynatrace-side configuration is needed:

```
App  ->  Bindplane collector (gen_ai_normalizer + transform)  ->  Dynatrace Grail
```

The app knows only about `http://localhost:4318`; the collector is the component that authenticates with Dynatrace (`DT_ENDPOINT`, `DT_API_TOKEN`) and forwards spans. The pipeline runs two processors (see [`otelcol-config.yaml`](otelcol-config.yaml)):

1. **`gen_ai_normalizer`** (source `openinference`, `remove_originals: true`) maps OpenInference attributes to `gen_ai.*` — including `llm.provider` / `llm.system` (both set to `cohere` by `CohereInstrumentor`) to `gen_ai.provider.name`. `remove_originals` drops the raw `llm.*` attributes so exported spans carry only `gen_ai.*` fields.
2. **`transform/response_model`** mirrors `gen_ai.request.model` to `gen_ai.response.model`, which the AI Observability app requires and OpenInference has no separate field for.

The collector is pinned to `ghcr.io/observiq/bindplane-agent:1.105.1` (Bindplane Distro for OpenTelemetry), which bundles the `gen_ai_normalizer` processor. The pin means a future version bump surfaces normalization changes in the e2e test.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker installed and running (runs the Bindplane collector)
- A Cohere API key (`COHERE_API_KEY`)
- Dynatrace tenant with an API token scoped to `openTelemetryTrace.ingest`

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install` — install dependencies
3. `make run` — start the collector, then the app on port 8000
4. `make request` — send a test haiku request (in a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DT_ENDPOINT` | Yes | — | Dynatrace tenant URL (e.g. `https://abc12345.live.dynatrace.com`) |
| `DT_API_TOKEN` | Yes | — | Dynatrace API token with `openTelemetryTrace.ingest` scope |
| `COHERE_API_KEY` | Yes | — | Cohere API key |
| `MODEL` | No | `command-r-08-2024` | Cohere model to use |
| `OTEL_SERVICE_NAME` | No | `cohere-haiku-writer` | Service name reported in traces |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Start the Bindplane collector, then run the app on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make stop` | Stop and remove the OTel collector container |
| `make logs` | Tail collector logs |
| `make help` | Show all available targets |

## Attribute mapping reference

The `gen_ai_normalizer` processor (source `openinference`) applies these translations, then `remove_originals` drops the source `llm.*` attributes. The collector config adds the `gen_ai.response.model` mirror.

| OpenInference source | Dynatrace target |
|---|---|
| `llm.token_count.prompt` | `gen_ai.usage.input_tokens` |
| `llm.token_count.completion` | `gen_ai.usage.output_tokens` |
| `llm.model_name` | `gen_ai.request.model` |
| `llm.provider` / `llm.system` (both `cohere`) | `gen_ai.provider.name` |
| tool-call id and function arguments | `gen_ai.tool.call.id` / `gen_ai.tool.call.arguments` |
| `session.id` | `gen_ai.conversation.id` |
| `openinference.span.kind` (`LLM`) | `gen_ai.operation.name` (`chat`) |
| `llm.input_messages.N.*` / `llm.output_messages.N.*` | `gen_ai.input.messages` / `gen_ai.output.messages` (full reconstruction, including roles, text parts, and tool calls) |
| _(added by collector config)_ | `gen_ai.response.model` (mirrored from `gen_ai.request.model`) |

`session.id` and `user.id` already match the OTel standard and pass through unchanged.

## Metrics

OpenInference is span-only by design (its instrumentors emit no metric instruments), so the two metrics the AI Observability app charts are derived from the spans (see [`otelcol-config.yaml`](otelcol-config.yaml)):

| Metric | Derived via |
|---|---|
| `gen_ai.client.operation.duration` (s) | `span_metrics` connector, on LLM spans |
| `gen_ai.client.token.usage` (`gen_ai.token.type` = `input`/`output`) | `signal_to_metrics` connector, two sum defs |

Both read the normalized `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` (mapped from OpenInference's `llm.token_count.*`). Both metrics use delta temporality — Dynatrace rejects cumulative.

## Known gaps & limitations

The `gen_ai_normalizer` `openinference` source does not set the following attributes. They are optional for the AI Observability app, and are candidates for upstream contribution to the processor:

- `gen_ai.request.temperature` / `gen_ai.request.top_p` / `gen_ai.request.max_tokens`
- `gen_ai.response.finish_reasons`
- `gen_ai.prompt_caching` and `gen_ai.cache.type` (Cohere does not support prompt caching today, so this gap does not apply in practice)

To close any of these locally, add statements to the `transform` processor in [`otelcol-config.yaml`](otelcol-config.yaml).

## Troubleshooting

**No spans in Dynatrace:**
- Confirm `DT_ENDPOINT` and `DT_API_TOKEN` are correctly set.
- Confirm the token has `openTelemetryTrace.ingest` permission.
- Check collector logs with `make logs` or `docker logs bindplane-otel-collector`.

**Collector crashes on startup:**
- Run `docker ps -a` and `docker logs bindplane-otel-collector` to see the error.
- Confirm Docker is running and port `4318` is free: `lsof -i :4318`.

**Spans visible in Distributed Tracing but not in AI Observability:**
- AI Observability requires `gen_ai.provider.name` (or `gen_ai.system`) to be set on the span — `gen_ai_normalizer` sets `gen_ai.provider.name` from `llm.provider`.
- Confirm the `gen_ai_normalizer` processor ran — the raw `llm.*` attributes should be gone and `gen_ai.*` attributes present in the collector debug output (`make logs`).

**Port conflict:**
- Ensure nothing else is listening on `4318`: `lsof -i :4318`.
