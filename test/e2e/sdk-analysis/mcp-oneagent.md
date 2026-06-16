# MCP + LangGraph — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `mcp/oneagent/ai-agent/main.py` | **Profile**: azure | **Dashboard**: `azureai.dashboard.json`

## Instrumentation

- **Library**: `langchain_mcp_adapters` + `langgraph` (`create_react_agent`) + `traceloop-sdk` WITHOUT `should_enrich_metrics`. LangChain instrumented via Traceloop.
- **Provider**: Azure OpenAI (`azure_openai` via `init_chat_model`, deployment from `AZURE_OPENAI_DEPLOYMENT`)
- **OTel setup**: `setup_tracing("mcp-agent-demo")` called from `dynatrace.py`. `Traceloop.init(app_name="mcp-agent-demo", ...)` with `resource_attributes={"gen_ai.agent.name": "mcp-agent-demo", "service.name": "mcp-agent-demo", "service.version": "0.0.1"}`. **No `should_enrich_metrics=True`**. Endpoint from `OTEL_ENDPOINT` env var.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | via `gen_ai.system` = "openai" (Traceloop LangChain instrumentor for Azure OpenAI) |
| `service.name` | ✅ | set to "mcp-agent-demo" via resource_attributes |
| `gen_ai.request.model` | ✅ | emitted by Traceloop's LangChain instrumentor |
| `gen_ai.response.model` | ✅ | emitted by Traceloop's LangChain instrumentor |
| `gen_ai.usage.input_tokens` | ⚠️ via fallback | emits `gen_ai.usage.prompt_tokens` (deprecated AR-026); DT accepts as fallback |
| `gen_ai.usage.output_tokens` | ⚠️ via fallback | emits `gen_ai.usage.completion_tokens` (deprecated AR-027); DT accepts as fallback |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + required fields all present (via fallbacks) |
| Prompts — content | ⚠️ legacy | `gen_ai.prompt.0.content` + `gen_ai.completion.0.content` via Traceloop; DT falls back to these |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ❌ | No `should_enrich_metrics=True` → `gen_ai.client.operation.duration` metric not emitted |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens` present on spans (AR-006/AR-007 via fallback) |
| Cost dashboard (metric) | ❌ | No `gen_ai.client.token.usage` metric (AR-044) — `should_enrich_metrics=True` not set |
| Service health tile | ⚠️ | `span.status_code` (AR-047) auto-emitted by OTel SDK; functional if Traceloop OTel SDK is correctly initialised |
| Agent quick filter | ❌ | `gen_ai.agent.name` is set on the Resource (not as a per-span attribute); DT's agent quick filter reads the span attribute, not the resource attribute — filter may be empty |
| Provider quick filter | ✅ | `gen_ai.system` present |
| Guardrails (Azure) | ❌ | `gen_ai.prompt.prompt_filter_results` and `gen_ai.completion.content_filter_results` not emitted |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | N/A | Azure profile — not applicable |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ⚠️ Legacy content | Modern `gen_ai.input.messages` / `gen_ai.output.messages` missing; falls back to deprecated attributes |
| Latency charts (p99/mean) | ❌ Empty | `gen_ai.client.operation.duration` metric (AR-025) not emitted; `should_enrich_metrics=True` missing |
| Cost dashboard tiles | ❌ Empty | `gen_ai.client.token.usage` metric (AR-044) not emitted; `gen_ai.token.type` dimension absent |
| Service health tile | ⚠️ Partial | `span.status_code` (AR-047) may be present from OTel SDK auto-instrumentation |
| Azure guardrail cards | ❌ Empty | `gen_ai.prompt.prompt_filter_results` (AR-015) and `gen_ai.completion.content_filter_results` (AR-016) not emitted |
| Agent quick filter | ❌ Empty | `gen_ai.agent.name` (AR-010) set on Resource only, not per-span |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.client.operation.duration` | AR-025 | All latency charts empty |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost dashboard metric tiles show $0 — distinct from span token attributes AR-006/AR-007. Requires `should_enrich_metrics=True` or a custom MeterProvider. |
| `gen_ai.token.type` (metric dimension) | AR-024 | Cost dashboard shows no data |
| `gen_ai.agent.name` (as span attribute) | AR-010 | Agent quick filter empty; currently only on Resource |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping |
| `gen_ai.prompt.prompt_filter_results` | AR-015 | Azure guardrail cards empty |
| `gen_ai.completion.content_filter_results` | AR-016 | Azure guardrail cards empty |
| `span.status_code` | AR-047 | If OTel SDK not properly wired, all requests appear successful; no error signal in health tile |

## What to fix in the example app

**1. Add `should_enrich_metrics=True` (fixes latency + cost charts)**

This is the highest-impact fix. In `dynatrace.py`, change:

```python
Traceloop.init(
    app_name=service_name,
    api_endpoint=OTEL_ENDPOINT,
    headers=headers,
    resource_attributes=resource,
    # ADD THIS:
    should_enrich_metrics=True,
)
```

Also add delta temporality (already set in some demos, confirm it's present):

```python
os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
```

**2. `gen_ai.agent.name` — move from Resource to span attribute (fixes agent quick filter)**

Setting `gen_ai.agent.name` on the Resource makes it visible in service-level metadata but may not populate the per-span agent filter in DT AI Observability. Fix: also set it as a Traceloop association property so it appears on each span:

```python
from traceloop.sdk import Traceloop
Traceloop.set_association_properties({"gen_ai.agent.name": service_name})
```

This can be added in `dynatrace.py`'s `setup_tracing()` after `Traceloop.init()`.

**3. `gen_ai.conversation.id` — not emitted**

The demo runs a single-turn query. If extended to multi-turn, add conversation ID via Traceloop association properties before each agent invocation.

**4. MCP spans use `mcp.method.name` convention**

MCP tool call spans (from `langchain_mcp_adapters`) use `mcp.method.name` rather than `gen_ai.*` attributes. These are separate spans in the trace and will not appear in the AI Observability prompts table, but they are visible as child spans in the distributed trace view. This is by design and not a fixable gap at the app level.

**5. Azure guardrail attributes — library limitation**

Not emitted by Traceloop/LangChain. Same situation as openai-agents demo — requires manual extraction from Azure API response or a library update.
