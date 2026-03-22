---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', sans-serif;
    background-color: #ffffff;
    color: #1a1a2e;
  }
  section.lead {
    background-color: #1a1a2e;
    color: #ffffff;
  }
  section.lead h1 {
    color: #73be28;
    font-size: 2.2rem;
  }
  section.lead h2 {
    color: #b0c4de;
  }
  h1 { color: #1a1a2e; border-bottom: 3px solid #73be28; padding-bottom: 0.2em; }
  h2 { color: #1565c0; }
  code { background-color: #f4f4f4; border-radius: 4px; }
  pre { background-color: #1e1e2e; border-radius: 8px; }
  pre code { color: #cdd6f4; }
  .highlight { color: #73be28; font-weight: bold; }
  table { font-size: 0.85em; }
---

<!-- _class: lead -->

# Instrumenting a LiteLLM Gateway
## OpenTelemetry → Dynatrace

**LiteLLM + FastAPI + Traceloop SDK**

---

# Agenda

1. **What is LiteLLM?** — Why we're using it
2. **The Instrumentation Challenge** — What doesn't work out of the box
3. **Two Approaches** — Option A vs Option B
4. **What We Built** — Live code walkthrough
5. **Signals in Dynatrace** — Traces, Metrics, Logs
6. **Key Learnings & Gotchas**

---

# What is LiteLLM?

LiteLLM is a **unified LLM proxy/router** that translates one OpenAI-compatible API call to any provider.

```
POST /chat/completions  →  LiteLLM  →  OpenAI  /  Anthropic  /  Groq  /  xAI
```

**Why use it at Dynatrace?**
- Swap providers without changing client code
- Centralise cost tracking, rate limiting, retries
- One gateway for many teams/models

```python
# Same call — any provider
litellm.completion(model="groq/llama-3.3-70b-versatile", messages=[...])
litellm.completion(model="xai/grok-2-latest",            messages=[...])
litellm.completion(model="anthropic/claude-3-5-sonnet",  messages=[...])
```

---

# The Instrumentation Challenge

**Traceloop's OpenLLMetry does NOT natively instrument LiteLLM.**

It auto-instruments these directly:

| ✅ Supported | ❌ Not LiteLLM |
|---|---|
| `openai`, `anthropic`, `cohere` | `litellm` (it's a router) |
| `groq`, `bedrock`, `vertexai` | |

LiteLLM sits *above* those SDKs — it's a router, not a provider SDK.

> **If you just call `Traceloop.init()` with LiteLLM, you get FastAPI spans but no `gen_ai.*` LLM spans.**

---

# Two Options

## Option A — LiteLLM's Built-in OTEL Callback ✅ (chosen)

```python
from litellm.integrations.opentelemetry import OpenTelemetry as LiteLLMOTel

litellm.callbacks = [LiteLLMOTel()]
```
→ Auto-captures `gen_ai.*` spans for every `litellm.completion()` call.
→ No manual spans needed. Works alongside Traceloop.

---

# Two Options (cont.)

## Option B — `openinference-instrumentation-litellm`

```python
pip install openinference-instrumentation-litellm
```

```python
from openinference.instrumentation.litellm import LiteLLMInstrumentor

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
)
LiteLLMInstrumentor().instrument(tracer_provider=provider)
```
→ OTel-native instrumentor pattern.
→ More control, but requires managing your own `TracerProvider`.

---

# What We Built — Stack Overview

```
  ┌─────────────────────────────────────────────┐
  │           FastAPI Application               │
  │   POST /chat/completions                    │
  │                                             │
  │   ┌─────────────────────────────────────┐   │
  │   │      LiteLLM Completion             │   │
  │   │  ┌──────────┐  ┌──────────────────┐ │   │
  │   │  │ LiteLLMOTel  │  │  httpx calls     │ │   │
  │   │  │ Callback  │  │  (auto-instrumented│ │   │
  │   │  └──────────┘  └──────────────────┘ │   │
  │   └─────────────────────────────────────┘   │
  └──────────────┬──────────────────────────────┘
                 │  OTLP gRPC :4317
        ┌────────▼────────┐
        │  OTel Collector │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   Dynatrace     │
        └─────────────────┘
```

---

# Initialisation — Order Matters

```python
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# ⚠️ MUST come before importing litellm
# LiteLLM creates httpx clients at import time
HTTPXClientInstrumentor().instrument()

import litellm
from litellm.integrations.opentelemetry import OpenTelemetry as LiteLLMOTel

# Register LiteLLM's built-in OTEL callback
litellm.callbacks = [LiteLLMOTel()]
```

> **Gotcha #1:** If you instrument httpx *after* litellm imports, the already-created httpx clients won't be wrapped — you lose HTTP-level spans.

---

# Traceloop SDK Init

```python
from traceloop.sdk import Traceloop
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

Traceloop.init(
    app_name="litellm-gateway",
    api_endpoint=os.environ["TRACELOOP_BASE_URL"],  # OTLP endpoint
    api_key="KEY",
    disable_batch=True,           # useful for dev — flush immediately
    should_enrich_metrics=True,   # adds resource attributes to metrics
    metrics_exporter=OTLPMetricExporter(
        endpoint="http://localhost:4317"
    ),
)
```

Traceloop initialises the global `TracerProvider` and `MeterProvider`.
The `LiteLLMOTel` callback and custom meters **share** these providers.

---

# FastAPI Instrumentation

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)
```

**What you get automatically:**
- `http.server.request.duration` histogram
- Span per HTTP request with: method, route, status code
- Trace context propagated from inbound `traceparent` headers

> Every `/chat/completions` POST becomes the **root span**.
> LiteLLM's `gen_ai.*` spans attach as **child spans** automatically.

---

# Custom Metrics

```python
from opentelemetry import metrics

_meter = metrics.get_meter("litellm-gateway")

_request_counter   = _meter.create_counter(
    "llm.requests", description="Total chat completion requests")

_error_counter     = _meter.create_counter(
    "llm.errors", description="Failed chat completion requests")

_duration_histogram = _meter.create_histogram(
    "llm.request.duration", unit="s",
    description="Duration of chat completion requests")

_token_counter     = _meter.create_counter(
    "llm.tokens", description="Tokens used, split by type")
```

---

# Custom Metrics — Recording

```python
@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    attrs = {"model": request.model}
    _request_counter.add(1, attrs)
    start = time.time()

    try:
        response = litellm.completion(**kwargs)
        _duration_histogram.record(time.time() - start, attrs)

        usage = getattr(response, "usage", None)
        if usage:
            _token_counter.add(usage.prompt_tokens or 0,
                               {**attrs, "token.type": "input"})
            _token_counter.add(usage.completion_tokens or 0,
                               {**attrs, "token.type": "output"})
        return response

    except Exception as e:
        _error_counter.add(1, attrs)
        raise HTTPException(status_code=500, detail=str(e))
```

---

# Log Forwarding via OTLP

```python
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

# Wire Python's logging module → OTLP collector
_log_provider = LoggerProvider()
_log_provider.add_log_record_processor(
    BatchLogRecordProcessor(
        OTLPLogExporter(endpoint="http://localhost:4317")
    )
)
set_logger_provider(_log_provider)
logging.basicConfig(level=logging.INFO)
logging.getLogger().addHandler(LoggingHandler(logger_provider=_log_provider))

logger = logging.getLogger("litellm-gateway")
logger.info("chat request: model=%s", request.model)
```

Logs are **correlated with traces** — they carry the active `trace_id`.

---

# Signals Summary

| Signal | Source | Key Attributes |
|---|---|---|
| **Traces** | FastAPIInstrumentor | `http.method`, `http.route`, `http.status_code` |
| **Traces** | LiteLLMOTel callback | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| **Traces** | HTTPXClientInstrumentor | Outbound HTTP to LLM APIs |
| **Metrics** | Custom meter | `llm.requests`, `llm.errors`, `llm.request.duration`, `llm.tokens` |
| **Metrics** | Traceloop enriched | `gen_ai.*` metric dimensions |
| **Logs** | Python `logging` + OTLPLogExporter | Correlated with `trace_id` |

---

# Environment Configuration

```bash
# Required
export TRACELOOP_BASE_URL="https://<your-dt-tenant>/api/v2/otlp"

# LLM provider keys (add what you need)
export XAI_API_KEY="xai-..."
export GROQ_API_KEY="gsk_..."

# LiteLLMOTel can also be configured via env vars:
export OTEL_EXPORTER=otlp_grpc
export OTEL_ENDPOINT=http://localhost:4317
```

No code changes needed to swap the OTLP endpoint — point at:
- Local OTel Collector → Dynatrace
- Dynatrace OTLP ingestion directly

---

# Key Learnings & Gotchas

| # | Gotcha | Solution |
|---|---|---|
| 1 | httpx clients created at LiteLLM import time | Instrument httpx **before** importing litellm |
| 2 | Traceloop has no native LiteLLM instrumentor | Use `LiteLLMOTel()` callback |
| 3 | Double instrumentation with manual spans | Delete manual `with tracer.start_as_current_span(...)` — callback handles it |
| 4 | `MeterProvider` not ready at `metrics.get_meter()` | Call `Traceloop.init()` **before** creating meters |
| 5 | Logs not correlated without trace context | Use `OTLPLogExporter` + `LoggingHandler` from OTel SDK |

---

# Full Dependency Picture

```
litellm==1.82.2
fastapi==0.135.1
traceloop-sdk==0.53.0

# OTel core
opentelemetry-sdk==1.40.0
opentelemetry-exporter-otlp-proto-grpc==1.40.0

# Auto-instrumentors
opentelemetry-instrumentation-fastapi==0.61b0
opentelemetry-instrumentation-httpx==0.61b0

# Semantic conventions for AI
opentelemetry-semantic-conventions-ai==0.4.15
```

`traceloop-sdk` pulls in the full OpenLLMetry instrumentor suite for
OpenAI, Anthropic, Groq, Bedrock, etc. — useful if you later bypass LiteLLM.

---

<!-- _class: lead -->

# What You See in Dynatrace

→ Add screenshots here

- Distributed trace: FastAPI root span + gen_ai child spans
- `gen_ai.usage.input_tokens` / `output_tokens` on spans
- `llm.request.duration` P50/P95 by model
- `llm.tokens` by `token.type` dimension
- Logs correlated to traces via `trace_id`

---

<!-- _class: lead -->

# Questions?

**Repo:** `litellm-demo2`
**Stack:** LiteLLM · FastAPI · Traceloop SDK · OpenTelemetry · Dynatrace

```
The signal chain:
  FastAPI → LiteLLM → httpx → LLM Provider
     ↓          ↓        ↓
  OTel spans + gen_ai.* spans + HTTP spans
                 ↓
           OTLP Collector
                 ↓
           Dynatrace
```