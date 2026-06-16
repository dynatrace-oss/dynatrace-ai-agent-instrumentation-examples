# OpenAI + OpenInference — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `openai/openinference/app.py` | **Profile**: openinference-basic (generic + openai) | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `openinference-instrumentation-openai` (OpenAIInstrumentor)
- **Provider**: OpenAI (or Azure-compatible via `OPENAI_API_BASE`)
- **OTel setup**: Manual `TracerProvider` with `OTLPSpanExporter` via `OTEL_EXPORTER_OTLP_ENDPOINT`. No Traceloop. No metrics pipeline configured.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | via `gen_ai.system` = "openai" |
| `service.name` | ✅ | set to "openinference" via `Resource.create()` |
| `gen_ai.request.model` | ✅ | emitted by OpenAIInstrumentor |
| `gen_ai.response.model` | ✅ | emitted by OpenAIInstrumentor |
| `gen_ai.usage.input_tokens` | ⚠️ via fallback | emits `gen_ai.usage.prompt_tokens` (deprecated AR-026); DT accepts as fallback |
| `gen_ai.usage.output_tokens` | ⚠️ via fallback | emits `gen_ai.usage.completion_tokens` (deprecated AR-027); DT accepts as fallback |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + required fields all present (via fallbacks) |
| Prompts — content | ⚠️ legacy | `gen_ai.prompt.0.content` + `gen_ai.completion.0.content` emitted; DT falls back to these |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ❌ | No `gen_ai.client.operation.duration` metric; no metrics pipeline at all |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens` present on spans (AR-006/AR-007 via fallback) |
| Cost dashboard (metric) | ❌ | No `gen_ai.client.token.usage` metric (AR-044); no metrics pipeline configured |
| Service health tile | ⚠️ | `span.status_code` (AR-047) auto-emitted by OTel SDK; functional if TracerProvider is correctly wired |
| Agent quick filter | ❌ | No `gen_ai.agent.name` emitted |
| Provider quick filter | ✅ | `gen_ai.system` = "openai" present |
| Guardrails (Azure) | N/A | Not Azure profile; `gen_ai.system` = "openai" even if Azure endpoint used |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | ❌ | No `gen_ai.prompt_caching` or `gen_ai.cache.type` emitted |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ⚠️ Legacy content | Modern `gen_ai.input.messages` / `gen_ai.output.messages` missing; falls back to deprecated attributes |
| Latency charts (p99/mean) | ❌ Empty | `gen_ai.client.operation.duration` metric (AR-025) not emitted; no metrics pipeline |
| Cost dashboard tiles | ❌ Empty | `gen_ai.client.token.usage` metric (AR-044) not emitted; no metrics pipeline. Note: span token attributes AR-006/AR-007 are present (via fallback) but the cost dashboard metric tiles require the OTel metric, not span attributes. |
| Service health tile | ⚠️ Partial | `span.status_code` (AR-047) auto-emitted by OTel SDK if TracerProvider is wired correctly |
| Agent quick filter | ❌ Empty | `gen_ai.agent.name` (AR-010) not emitted — direct LLM call, no agent |
| Cache hit rate chart | ❌ Empty | `gen_ai.prompt_caching` (AR-022) and `gen_ai.cache.type` (AR-023) not emitted |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.client.operation.duration` | AR-025 | All latency charts empty |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost dashboard metric tiles show $0 silently — distinct from span token attributes AR-006/AR-007. Requires a metrics pipeline (e.g. Traceloop `should_enrich_metrics=True` or custom `MeterProvider`). |
| `gen_ai.token.type` (metric dimension) | AR-024 | Cost dashboard shows no data |
| `gen_ai.agent.name` | AR-010 | Agent quick filter empty; all spans classified as LLM only |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping in prompts view |

## What to fix in the example app

**1. Add a metrics pipeline (fixes latency + cost charts)**

OpenInference does not emit `gen_ai.client.operation.duration` or `gen_ai.client.token.usage`. These are metric-level signals. To fix, either:

- Switch to Traceloop (`Traceloop.init(..., should_enrich_metrics=True)`) which synthesises these metrics from spans, or
- Add a custom `MeterProvider` with `OTLPMetricExporter` and manually record `gen_ai.client.operation.duration` per call. This is a library limitation — OpenInference has no built-in metric enrichment equivalent to Traceloop's `should_enrich_metrics`.

**2. Use modern token attribute names (optional, improves forward compatibility)**

`gen_ai.usage.prompt_tokens` → `gen_ai.usage.input_tokens`
`gen_ai.usage.completion_tokens` → `gen_ai.usage.output_tokens`

This is a library limitation; the OpenInference instrumentation emits legacy names. No code change in `app.py` can fix this without patching the library or post-processing spans.

**3. `gen_ai.agent.name` is not applicable here** — this is a direct LLM call demo, not an agent. No fix needed.

**4. Cache hit rate** — `gen_ai.prompt_caching` and `gen_ai.cache.type` are not emitted by OpenInference. This is a library limitation.
