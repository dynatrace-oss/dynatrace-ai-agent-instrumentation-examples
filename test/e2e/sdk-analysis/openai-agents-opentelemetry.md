# OpenAI Agents SDK — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `openai-agents/opentelemetry/` (main.py + api.py) | **Profile**: azure | **Dashboard**: `azureai.dashboard.json`

## Instrumentation

- **Library**: `openai-agents` (Agents SDK) + `traceloop-sdk` with `should_enrich_metrics=True`
- **Provider**: Azure OpenAI (`AsyncAzureOpenAI` client, deployment `gpt-4o`)
- **OTel setup**: `Traceloop.init(app_name="openai-cs-agents", ..., should_enrich_metrics=True, disable_batch=True)` in `api.py`. Delta temporality set via `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`. OTel logs pipeline also configured. Reads DT token from `/etc/secrets/dynatrace_otel`.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | via `gen_ai.system` = "openai" (Traceloop) |
| `service.name` | ✅ | set to "openai-cs-agents" via `Traceloop.init(app_name=...)` |
| `gen_ai.request.model` | ✅ | emitted by Traceloop's OpenAI instrumentor |
| `gen_ai.response.model` | ✅ | emitted by Traceloop's OpenAI instrumentor |
| `gen_ai.usage.input_tokens` | ⚠️ via fallback | emits `gen_ai.usage.prompt_tokens` (deprecated AR-026); DT accepts as fallback |
| `gen_ai.usage.output_tokens` | ⚠️ via fallback | emits `gen_ai.usage.completion_tokens` (deprecated AR-027); DT accepts as fallback |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + required fields all present (via fallbacks) |
| Prompts — content | ⚠️ legacy | `gen_ai.prompt.0.content` + `gen_ai.completion.0.content` via Traceloop; DT falls back to these |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ✅ | `should_enrich_metrics=True` → `gen_ai.client.operation.duration` histogram emitted |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens` present on spans (AR-006/AR-007 via fallback) |
| Cost dashboard (metric) | ✅ | `should_enrich_metrics=True` → `gen_ai.client.token.usage` metric (AR-044) with `gen_ai.token.type` dimension emitted by Traceloop |
| Service health tile | ✅ | `span.status_code` (AR-047) auto-emitted by OTel SDK |
| Agent quick filter | ✅ | OpenAI Agents SDK emits agent names; Traceloop captures `gen_ai.agent.name` |
| Provider quick filter | ✅ | `gen_ai.system` = "openai" present |
| Guardrails (Azure) | ❌ | `gen_ai.prompt.prompt_filter_results` and `gen_ai.completion.content_filter_results` not emitted; Azure Content Safety not configured |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | ❌ | No `gen_ai.prompt_caching` or `gen_ai.cache.type` emitted |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ⚠️ Legacy content | Modern `gen_ai.input.messages` / `gen_ai.output.messages` missing; falls back to deprecated attributes |
| Latency charts (p99/mean) | ✅ Yes | `gen_ai.client.operation.duration` emitted via `should_enrich_metrics=True` |
| Cost dashboard tiles | ✅ Yes | `gen_ai.client.token.usage` metric (AR-044) emitted via `should_enrich_metrics=True` |
| Service health tile | ✅ Yes | `span.status_code` (AR-047) auto-emitted by OTel SDK |
| Azure guardrail cards | ❌ Empty | `gen_ai.prompt.prompt_filter_results` (AR-015) and `gen_ai.completion.content_filter_results` (AR-016) not emitted |
| Agent quick filter | ✅ Yes | `gen_ai.agent.name` captured by Traceloop |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.prompt.prompt_filter_results` | AR-015 | Azure guardrail cards empty |
| `gen_ai.completion.content_filter_results` | AR-016 | Azure guardrail cards empty |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping in prompts view (each request is isolated) |
| `gen_ai.request.temperature` | AR-042 | Model comparison dashboard missing temperature dimension |

## What to fix in the example app

**1. `gen_ai.conversation.id` — missing conversation threading**

The demo uses `session_id` internally (passed in the FastAPI request) but does not propagate it as `gen_ai.conversation.id` on spans. Fix: add a Traceloop association property before each agent run:

```python
from traceloop.sdk.tracing import get_tracer_provider
# or set as a span attribute on the outer span:
span.set_attribute("gen_ai.conversation.id", session_id)
```

Alternatively, pass it via `Traceloop.set_association_properties({"gen_ai.conversation.id": session_id})` at request time.

**2. `gen_ai.request.temperature` — missing model comparison dimension**

The agent config in `api.py` does not set temperature on the Azure OpenAI client. Fix: pass `temperature=0.7` (or whatever value is appropriate) when constructing `AsyncAzureOpenAI` or the agent runner, and ensure Traceloop's instrumentor captures it (it should automatically for standard OpenAI API calls).

**3. Azure guardrail attributes — library limitation**

`gen_ai.prompt.prompt_filter_results` and `gen_ai.completion.content_filter_results` are Azure Content Filter response fields. Traceloop does not currently emit these automatically. Fix would require either: (a) configuring Azure Content Safety and manually extracting + setting span attributes from the API response, or (b) a Traceloop library update. No simple code change in `api.py` alone.

**4. Token attribute names — library limitation**

Traceloop emits legacy `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens`. DT accepts these as fallbacks. No action needed unless strict modern semconv compliance is required.
