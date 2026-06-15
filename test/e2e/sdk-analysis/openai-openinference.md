# OpenAI + OpenInference — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.1.1 | **Path**: `openai/openinference/app.py` | **Profile**: openinference-basic (generic + openai)

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
| Cost dashboard | ❌ | No `gen_ai.client.token.usage` metric with `gen_ai.token.type` dimension |
| Agent quick filter | ❌ | No `gen_ai.agent.name` emitted |
| Provider quick filter | ✅ | `gen_ai.system` = "openai" present |
| Guardrails (Azure) | N/A | Not Azure profile; `gen_ai.system` = "openai" even if Azure endpoint used |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | ❌ | No `gen_ai.prompt_caching` or `gen_ai.cache.type` emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.client.operation.duration` | All latency charts empty |
| `gen_ai.token.type` (metric dimension) | Cost dashboard shows no data |
| `gen_ai.agent.name` | Agent quick filter empty; all spans classified as LLM only |
| `gen_ai.conversation.id` | No conversation thread grouping in prompts view |

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
