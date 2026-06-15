# Google ADK (Academic Research Agent) — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.1.1 | **Path**: `google-adk/opentelemetry/` (`__init__.py` + `agent.py`) | **Profile**: generic (Google Vertex AI / Gemini)

## Instrumentation

- **Library**: `google-adk` (`google.adk.agents.LlmAgent`) + `traceloop-sdk`. Traceloop's Vertex AI / Google GenAI instrumentor wraps Gemini API calls.
- **Provider**: Google Vertex AI / Gemini (`MODEL = "gemini-2.5-pro"`)
- **OTel setup**: `Traceloop.init(app_name="google-adk-samples", api_endpoint="https://wkf10640.live.dynatrace.com/api/v2/otlp", disable_batch=True, headers=headers)` in `__init__.py`. **No `should_enrich_metrics=True`**. DT endpoint is hardcoded. Token read from `/etc/secrets/dynatrace_otel`. Delta temporality set via env var.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | via `gen_ai.system` = "google_vertex_ai" or similar (Traceloop Vertex AI instrumentor) |
| `service.name` | ✅ | set to "google-adk-samples" via `Traceloop.init(app_name=...)` |
| `gen_ai.request.model` | ✅ | emitted by Traceloop's Vertex AI / Google instrumentor |
| `gen_ai.response.model` | ✅ | emitted by Traceloop's Vertex AI / Google instrumentor |
| `gen_ai.usage.input_tokens` | ⚠️ via fallback | emits `gen_ai.usage.prompt_tokens` (deprecated AR-026); DT accepts as fallback |
| `gen_ai.usage.output_tokens` | ⚠️ via fallback | emits `gen_ai.usage.completion_tokens` (deprecated AR-027); DT accepts as fallback |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + required fields all present (via fallbacks) |
| Prompts — content | ⚠️ legacy | `gen_ai.prompt.0.content` + `gen_ai.completion.0.content` via Traceloop; DT falls back to these |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ❌ | No `should_enrich_metrics=True` → `gen_ai.client.operation.duration` metric not emitted |
| Cost dashboard | ❌ | No `gen_ai.client.token.usage` metric with `gen_ai.token.type` dimension |
| Agent quick filter | ✅ | ADK agent names (`academic_coordinator`, sub-agents) captured by Traceloop's ADK instrumentor |
| Provider quick filter | ✅ | `gen_ai.system` present |
| Guardrails (Azure) | N/A | Not Azure |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | N/A | Not OpenAI |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.client.operation.duration` | All latency charts empty |
| `gen_ai.token.type` (metric dimension) | Cost dashboard shows no data |
| `gen_ai.conversation.id` | No conversation thread grouping |

## What to fix in the example app

**1. Add `should_enrich_metrics=True` (fixes latency + cost charts)**

This is the highest-impact and easiest fix. In `__init__.py`, change:

```python
Traceloop.init(
    app_name="google-adk-samples",
    api_endpoint="https://wkf10640.live.dynatrace.com/api/v2/otlp",
    disable_batch=True,
    headers=headers,
    # ADD THIS:
    should_enrich_metrics=True,
)
```

This causes Traceloop to synthesise `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` (with `gen_ai.token.type`) from span data, populating latency charts and the cost dashboard in DT.

**2. Hardcoded DT endpoint in `__init__.py`**

`api_endpoint="https://wkf10640.live.dynatrace.com/api/v2/otlp"` is hardcoded. Fix: read from environment variable:

```python
import os
DT_ENDPOINT = os.environ.get("DT_ENDPOINT", "https://wkf10640.live.dynatrace.com/api/v2/otlp")
Traceloop.init(
    app_name="google-adk-samples",
    api_endpoint=DT_ENDPOINT,
    ...
)
```

**3. `gen_ai.conversation.id` — not emitted**

ADK agent runs are typically single-turn in this demo. If extended to multi-turn conversations, add conversation ID tracking via Traceloop association properties.

**4. Token attribute names — library limitation**

Traceloop emits legacy token names. DT accepts them as fallbacks. No app-level fix needed.
