# LiteLLM + FastAPI — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `litellm/opentelemetry/fastapi-instrumentation/main.py` | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `litellm` with `LiteLLMOTel` callback + `traceloop-sdk` with `should_enrich_metrics=True`. FastAPI instrumented via `FastAPIInstrumentor`. `HTTPXClientInstrumentor` applied before litellm import.
- **Provider**: Multi-provider (OpenAI, xAI Grok, Groq — selected per request model string). No fixed provider.
- **OTel setup**: `Traceloop.init(app_name="litellm-gateway", ..., should_enrich_metrics=True, disable_batch=True, metrics_exporter=OTLPMetricExporter(...))` + `LiteLLMOTel()` registered as `litellm.callbacks`. Custom metrics (`llm.requests`, `llm.errors`, `llm.request.duration`, `llm.tokens`) added on top. OTel logs pipeline to OTLP gRPC. Sends to `COLLECTOR_BASE_URL` (required env var).

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | `LiteLLMOTel` + Traceloop emit `gen_ai.system` per provider |
| `service.name` | ✅ | set to "litellm-gateway" via `Traceloop.init(app_name=...)` |
| `gen_ai.request.model` | ✅ | emitted by LiteLLMOTel callback |
| `gen_ai.response.model` | ✅ | emitted by LiteLLMOTel callback |
| `gen_ai.usage.input_tokens` | ⚠️ via fallback | LiteLLMOTel emits `gen_ai.usage.prompt_tokens` (legacy); DT accepts as fallback |
| `gen_ai.usage.output_tokens` | ⚠️ via fallback | LiteLLMOTel emits `gen_ai.usage.completion_tokens` (legacy); DT accepts as fallback |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + required fields all present (via fallbacks) |
| Prompts — content | ⚠️ legacy | `gen_ai.prompt.0.content` + `gen_ai.completion.0.content` via LiteLLMOTel/Traceloop; DT falls back to these |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ✅ | `should_enrich_metrics=True` → `gen_ai.client.operation.duration` emitted by Traceloop |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens` present on spans (AR-006/AR-007 via fallback) |
| Cost dashboard (metric) | ✅ | `should_enrich_metrics=True` → `gen_ai.client.token.usage` metric (AR-044) with `gen_ai.token.type` dimension emitted by Traceloop |
| Service health tile | ✅ | `span.status_code` (AR-047) auto-emitted by OTel SDK |
| Agent quick filter | ❌ | No `gen_ai.agent.name`; LiteLLM is an LLM gateway, not an agent framework |
| Provider quick filter | ✅ | `gen_ai.system` present per provider |
| Guardrails (Azure) | N/A | Not Azure profile |
| Guardrails (Bedrock) | N/A | Not Bedrock profile |
| Cache hit rate (OpenAI) | ❌ | No `gen_ai.prompt_caching` or `gen_ai.cache.type` emitted |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ⚠️ Legacy content | Modern `gen_ai.input.messages` / `gen_ai.output.messages` missing; falls back to deprecated attributes |
| Latency charts (p99/mean) | ✅ Yes | `gen_ai.client.operation.duration` emitted via `should_enrich_metrics=True` |
| Cost dashboard tiles | ✅ Yes | `gen_ai.client.token.usage` metric (AR-044) emitted via `should_enrich_metrics=True` |
| Service health tile | ✅ Yes | `span.status_code` auto-emitted by OTel SDK |
| Agent quick filter | ❌ Empty | `gen_ai.agent.name` (AR-010) not applicable — LiteLLM is a gateway, not an agent |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.agent.name` | AR-010 | Agent quick filter empty; not applicable for a gateway |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping; request model is stateless |
| `span.status_code` | AR-047 | Note: this IS auto-emitted by OTel SDK. If the OTel SDK pipeline is misconfigured, all requests would appear successful. |

## Note on custom metrics

The demo creates custom metrics (`llm.request.duration`, `llm.tokens`, `llm.requests`, `llm.errors`) in addition to `gen_ai.client.operation.duration`. DT's AI Observability views are keyed on `gen_ai.client.operation.duration` — the custom `llm.*` metrics are visible in generic DT metrics views but do **not** populate latency or token charts in the AI Observability app. Both metric sets coexist without conflict.

## What to fix in the example app

**1. `COLLECTOR_BASE_URL` must be set — add a clear error**

`COLLECTOR_BASE_URL` is read via `os.environ["COLLECTOR_BASE_URL"]` which raises `KeyError` with no useful message if unset. Fix: add a guard at startup:

```python
COLLECTOR_BASE_URL = os.environ.get("COLLECTOR_BASE_URL")
if not COLLECTOR_BASE_URL:
    raise ValueError("COLLECTOR_BASE_URL environment variable is required")
```

**2. `api_key="KEY"` placeholder in `Traceloop.init`**

`Traceloop.init(..., api_key="KEY", ...)` uses a literal string `"KEY"` — this is non-functional if Traceloop tries to use it. When sending to a local collector with no auth, this is harmless, but it is confusing. Remove it or read from env:

```python
api_key=os.environ.get("TRACELOOP_API_KEY", ""),
```

**3. `gen_ai.conversation.id` — not applicable for a stateless gateway**

LiteLLM is stateless per request. If the demo is extended to support sessions, add `gen_ai.conversation.id` as a span attribute by extracting it from the request header or body and setting it via Traceloop association properties.

**4. Token attribute names — library limitation**

LiteLLMOTel emits legacy token names. DT accepts them as fallbacks. No app-level fix.
