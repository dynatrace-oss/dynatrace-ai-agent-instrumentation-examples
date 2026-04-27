## FastAPI + LiteLLM Gateway

A FastAPI application that acts as an LLM gateway, routing chat completion requests to multiple providers via [LiteLLM](https://docs.litellm.ai/), with full OpenTelemetry observability exported to Dynatrace.

> [!TIP]
> For Dynatrace setup instructions, API token scopes, and advanced configuration, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

## Signals

| Signal | Source | Details |
|---|---|---|
| **Traces** | `FastAPIInstrumentor` + `HTTPXClientInstrumentor` + `LiteLLMOTel` callback | HTTP request spans, outbound LLM call spans with `gen_ai.*` attributes (model, tokens, cost, finish reason) |
| **Metrics** | Custom OTel instruments | `llm.requests`, `llm.errors`, `llm.request.duration` (s), `llm.tokens` (split by `input`/`output`) — all dimensioned by `model` |
| **Logs** | `LoggingHandler` | Python `logging` bridged to OTel; correlated to the active trace span |

All signals are forwarded via gRPC to a local OTel Collector at `localhost:4317`. See the [parent README](../README.md) for the collector configuration.

## How to use

### Prerequisites

- Python 3.9+
- A running [OpenTelemetry Collector](../README.md) forwarding to Dynatrace
- At least one LLM provider API key (xAI, Groq, or Anthropic)
- A Dynatrace environment with an API token that has the **`openTelemetryTrace.ingest`**, **`metrics.ingest`**, and **`logs.ingest`** scopes

### Configure environment

```bash
# Required — points to your local OTel Collector
export TRACELOOP_BASE_URL=http://localhost:4318

# At least one of these must be set
export XAI_API_KEY=<your-xai-key>              # for xai/grok-* models
export GROQ_API_KEY=<your-groq-key>            # for groq/* models
export ANTHROPIC_API_KEY=<your-anthropic-key>  # for anthropic/* models
```

### Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
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
