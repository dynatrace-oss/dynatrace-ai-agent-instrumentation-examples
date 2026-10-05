## FastAPI + LiteLLM Gateway

A FastAPI application that acts as an LLM gateway, routing chat completion requests to multiple providers via [LiteLLM](https://docs.litellm.ai/), with full OpenTelemetry observability exported to Dynatrace.

> [!TIP]
> For Dynatrace setup instructions, API token scopes, and advanced configuration, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

## Signals

| Signal | Source | Details |
|---|---|---|
| **Traces** | `FastAPIInstrumentor` + `HTTPXClientInstrumentor` + OpenInference `LiteLLMInstrumentor` | One HTTP server span per request, plus an LLM span with `gen_ai.*` attributes (model, provider, tokens, messages) and `session.id` from `conversation_id` |
| **Metrics** | Collector `span_metrics` / `signal_to_metrics` + custom OTel instruments | `gen_ai.client.operation.duration`, `gen_ai.client.token.usage` (derived from spans); `llm.requests`, `llm.errors`, `llm.request.duration` (s), `llm.tokens` (split by `input`/`output`) — all dimensioned by `model` |
| **Logs** | `LoggingHandler` | Python `logging` bridged to OTel; correlated to the active trace span |

All signals are forwarded via gRPC to a local OTel Collector at `localhost:4317`. See the [parent README](../README.md) for the collector configuration.

## How to use

### Prerequisites

- Python 3.9+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A running [OpenTelemetry Collector](../README.md) forwarding to Dynatrace
- At least one LLM provider API key (xAI, Groq, or Anthropic)
- A Dynatrace environment with an API token that has the **`openTelemetryTrace.ingest`**, **`metrics.ingest`**, and **`logs.ingest`** scopes

### Configure environment

```bash
# Required — points to your local OTel Collector
export COLLECTOR_BASE_URL=localhost:4317

# At least one of these must be set
export XAI_API_KEY=<your-xai-key>              # for xai/grok-* models
export GROQ_API_KEY=<your-groq-key>            # for groq/* models
export ANTHROPIC_API_KEY=<your-anthropic-key>  # for anthropic/* models
```

### Configure the OTel Collector

The shared [`otel-collector-config.yaml`](../otel-collector-config.yaml) fills `gen_ai.*` gaps from OpenInference's legacy attributes, then drops `llm.*`/`openinference.*`, and derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` from LLM spans. It needs the [Bindplane Distro for OpenTelemetry](https://github.com/observIQ/bindplane-otel-collector) for the `signal_to_metrics` connector. `make run` starts it for you; to start it by hand from `litellm/opentelemetry`:

```bash
docker run --rm \
  -p 127.0.0.1:4317:4317 \
  -p 127.0.0.1:4318:4318 \
  -v "$(pwd)/otel-collector-config.yaml:/etc/otelcol/otel-collector-config.yaml:ro" \
  -e DT_ENDPOINT \
  -e DT_API_TOKEN \
  ghcr.io/observiq/bindplane-agent:1.108.0 \
  --config=/etc/otelcol/otel-collector-config.yaml
```

### Run

```bash
cd litellm/opentelemetry/fastapi-instrumentation
make install
make run
```

### Call the API

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "groq/llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

Supported model prefixes: `xai/`, `groq/`, `anthropic/`, `ollama/`

### Verify in Dynatrace

```dql
fetch spans, from:now()-1h
| filter service.name == "litellm-gateway"
| sort timestamp desc
| limit 50
```
