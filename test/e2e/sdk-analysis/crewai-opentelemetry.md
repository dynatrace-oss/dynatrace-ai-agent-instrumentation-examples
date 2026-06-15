# CrewAI + OTel Collector — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.1.1 | **Path**: `crewai/opentelemetry/` (no .py source files — CrewAI CLI-based) | **Profile**: generic

## Instrumentation

- **Library**: `crewai==1.6.1` + `traceloop-sdk==0.49.5`. CrewAI CLI (`python -m crewai run`) bootstraps crew definitions from YAML config. Traceloop's CrewAI instrumentor wraps LLM calls and crew/agent/task spans automatically.
- **Provider**: Determined by crew YAML config (not fixed in source — typically OpenAI or Azure OpenAI)
- **OTel setup**: No application-level Python code to configure Traceloop directly. Traceloop is initialised as a library dependency when CrewAI loads. Telemetry is sent to a local OTel collector on `localhost:4318`. The collector (`dynatrace-otel-collector` container) applies `cumulativetodelta` processor before forwarding to DT. Collector config in `collector.config.yaml`. **No `should_enrich_metrics` flag** can be set from app code (no app code exists to modify).

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | Traceloop emits `gen_ai.system` per LLM provider (OpenAI, Azure, etc.) |
| `service.name` | ✅ | Traceloop sets service name from crew app name |
| `gen_ai.request.model` | ✅ | emitted by Traceloop's LLM instrumentor |
| `gen_ai.response.model` | ✅ | emitted by Traceloop's LLM instrumentor |
| `gen_ai.usage.input_tokens` | ⚠️ via fallback | emits `gen_ai.usage.prompt_tokens` (deprecated AR-026); DT accepts as fallback |
| `gen_ai.usage.output_tokens` | ⚠️ via fallback | emits `gen_ai.usage.completion_tokens` (deprecated AR-027); DT accepts as fallback |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + required fields all present (via fallbacks) |
| Prompts — content | ⚠️ legacy | `gen_ai.prompt.0.content` + `gen_ai.completion.0.content` via Traceloop; DT falls back to these |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ❌ | `should_enrich_metrics` cannot be set from app code (no .py source files); Traceloop default behaviour does not emit `gen_ai.client.operation.duration` metric |
| Cost dashboard | ❌ | No `gen_ai.client.token.usage` metric with `gen_ai.token.type` dimension emitted |
| Agent quick filter | ✅ | Traceloop's CrewAI instrumentor captures crew agent names as `gen_ai.agent.name` on agent-level spans |
| Provider quick filter | ✅ | `gen_ai.system` present |
| Guardrails (Azure) | N/A | No Azure Content Safety configured in crew |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | N/A | Not applicable for generic profile |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.client.operation.duration` | All latency charts empty — no metric enrichment without `should_enrich_metrics=True` |
| `gen_ai.token.type` (metric dimension) | Cost dashboard shows no data |
| `gen_ai.conversation.id` | No conversation thread grouping |

## Note on OTel collector cumulative → delta conversion

The `collector.config.yaml` applies the `cumulativetodelta` processor to metrics. This is correct for DT (which requires delta temporality). However, since Traceloop does not emit `gen_ai.client.operation.duration` or `gen_ai.client.token.usage` without `should_enrich_metrics=True`, the processor has no relevant gen_ai metrics to convert — the latency and cost charts remain empty regardless.

## What to fix in the example app

**1. Latency + cost charts — library/framework limitation (no Python source to modify)**

Since there are no `.py` source files (the crew is defined purely via CrewAI CLI YAML), `should_enrich_metrics=True` cannot be set in the conventional way. Options:

- **Option A**: Add a Python entry-point script (e.g., `run.py`) that calls `Traceloop.init(..., should_enrich_metrics=True)` before invoking `crewai.flow.kickoff()` or equivalent. This gives full control over Traceloop init.

- **Option B**: Set `TRACELOOP_METRICS_ENABLED=true` and any Traceloop environment variable equivalent for metric enrichment, if supported by the installed version.

- **Option C**: Add a custom OTel metric exporter in a wrapper script that synthesises `gen_ai.client.operation.duration` from span data before forwarding.

Option A is the most straightforward path and does not conflict with the CLI-based crew definition.

**2. `gen_ai.conversation.id` — not applicable for CLI batch execution**

CrewAI runs tasks in batch mode. If the demo is extended to support multi-turn or session-based interactions, add conversation ID tracking.

**3. Token attribute names — library limitation**

Traceloop emits legacy token names. DT accepts them as fallbacks. No fix needed for functional correctness.
