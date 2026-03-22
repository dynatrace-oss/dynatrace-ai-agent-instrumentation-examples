# `main.py`

A FastAPI application that acts as an LLM gateway, routing chat completion requests to multiple providers via LiteLLM, with full OpenTelemetry observability (traces, metrics, and logs) exported to a local OTLP collector.

---

## Endpoint

### `POST /chat/completions`

Accepts an OpenAI-compatible chat completion request and proxies it to the configured LLM provider via `litellm.completion()`.

**Request body:**
| Field | Type | Required |
|---|---|---|
| `model` | `string` | Yes — use provider-prefixed names (e.g. `groq/llama-3.1-8b-instant`, `xai/grok-2-latest`, `anthropic/claude-sonnet-4-6`, `ollama/llama3`) |
| `messages` | `ChatMessage[]` | Yes |
| `max_tokens` | `int` | No |
| `temperature` | `float` | No |

---

## Provider Configuration

API keys are read from environment variables at startup. Each is optional — only providers with a key set are enabled.

| Env var | Provider | Model prefix |
|---|---|---|
| `XAI_API_KEY` | xAI (Grok) | `xai/` |
| `GROQ_API_KEY` | Groq | `groq/` |
| `ANTHROPIC_API_KEY` | Anthropic | `anthropic/` |
| `TRACELOOP_BASE_URL` | Traceloop (required) | — |

---

## Observability

All signals are exported to the local OTLP collector at `http://localhost:4317`.

### Traces
- **`FastAPIInstrumentor`** — auto-instruments every HTTP request
- **`HTTPXClientInstrumentor`** — auto-instruments outbound HTTP calls made by LiteLLM (must be called before LiteLLM is imported)
- **`LiteLLMOTel` callback** — captures `gen_ai.*` span attributes (model, token counts, cost, finish reason) for every `litellm.completion()` call
- **Traceloop SDK** — enriches traces with additional LLM semantic conventions

### Metrics
Custom instruments on the `litellm-gateway` meter, all dimensioned by `model`:

| Metric | Type | Description |
|---|---|---|
| `llm.requests` | Counter | Total requests |
| `llm.errors` | Counter | Total failed requests |
| `llm.request.duration` | Histogram (s) | End-to-end completion latency |
| `llm.tokens` | Counter | Tokens used, split by `token.type`: `input` / `output` |

### Logs
Python `logging` is bridged to OTel via `LoggingHandler`, so all log records are exported as OTel log signals and automatically correlated to the active trace span. Three log events are emitted per request: request received, successful response, and error.

---

# Getting Traceloop to Auto-Instrument LiteLLM - No Manual Spans

Traceloop's OpenLLMetry does NOT have a native LiteLLM instrumentor. Its auto-instrumentation covers OpenAI, Anthropic, Cohere, Vertex, etc. directly — but LiteLLM is a proxy/router on top of those, and it's not in the supported auto-instrument list.

## Option A: Use LiteLLM's Built-in OTEL Callback (Cleanest)

This is the right path when LiteLLM is your gateway. Just set the callback and point it at your OTLP endpoint — no manual spans needed at all:

```python
import litellm
from litellm.integrations.opentelemetry import OpenTelemetry as LiteLLMOTel

# This one line auto-instruments every litellm.completion() call
litellm.callbacks = [LiteLLMOTel()]
```

Configure via env vars:

```
OTEL_EXPORTER=otlp_grpc
OTEL_ENDPOINT=http://localhost:4317
OTEL_HEADERS="api-key=your-traceloop-key"
```

## Option B: Use openinference-instrumentation-litellm

The `openinference-instrumentation-litellm` package implements OTel-compatible tracing for LiteLLM and is fully compatible with any OTLP collector:

```bash
pip install openinference-instrumentation-litellm
```

```python
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317")))

LiteLLMInstrumentor().instrument(tracer_provider=provider)
```

After this, every `litellm.completion()` call is automatically traced — no `with tracer.start_as_current_span(...)` needed.