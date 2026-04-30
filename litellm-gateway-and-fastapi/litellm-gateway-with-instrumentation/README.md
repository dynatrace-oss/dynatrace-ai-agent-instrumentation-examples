## LiteLLM Proxy Gateway

This example runs [LiteLLM's built-in proxy server](https://docs.litellm.ai/docs/simple_proxy) with Traceloop instrumentation and FastAPI auto-instrumentation, routing requests to Ollama (local) and Anthropic.

> [!TIP]
> For Dynatrace setup instructions, API token scopes, and advanced configuration, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

## Signals

| Signal | Source | Details |
|---|---|---|
| **Traces** | `FastAPIInstrumentor` + Traceloop + LiteLLM `success_callback: ["otel"]` | HTTP spans + per-request LLM spans with `gen_ai.*` attributes |
| **Metrics** | Traceloop SDK | LLM usage metrics via `should_enrich_metrics=True` |

All signals are forwarded via gRPC to a local OTel Collector at `localhost:4317`. See the [parent README](../README.md) for the collector configuration.

## Configured models

| Name | Provider | Notes |
|---|---|---|
| `ollama-llama3.2` | Ollama (local) | Requires Ollama running at `localhost:11434` |
| `claude-sonnet-4-6` | Anthropic | Requires `ANTHROPIC_API_KEY` |
| `rag-embeddings` | Ollama (local) | `all-minilm` embedding model |

## How to use

### Prerequisites

- Python 3.9+
- [Ollama](https://ollama.com) running locally (`ollama serve`) with `llama3.2` and `all-minilm` pulled
- A running [OpenTelemetry Collector](../README.md) forwarding to Dynatrace
- A Dynatrace environment with an API token that has the **`openTelemetryTrace.ingest`** and **`metrics.ingest`** scopes

### Configure environment

```bash
export TRACELOOP_BASE_URL=http://localhost:4318
export ANTHROPIC_API_KEY=<your-anthropic-key>
export LITELLM_MASTER_KEY=<choose-a-master-key>    # required to call the proxy
export LITELLM_UI_USERNAME=admin
export LITELLM_UI_PASSWORD=<choose-a-password>
```

### Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 basic.py
```

The proxy starts on `http://localhost:4000`. The Admin UI is available at `http://localhost:4000/ui`.

### Call the proxy

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <LITELLM_MASTER_KEY>" \
  -d '{
    "model": "ollama-llama3.2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Verify in Dynatrace

```dql
fetch spans, from:now()-1h
| filter service.name == "litellm-gateway"
| sort timestamp desc
| limit 50
```
