# MCP + LangGraph — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `mcp/opentelemetry/ai-agent/server.py` | **Profile**: generic | **Dashboard**: `genai.dashboard.json`

## Instrumentation

- **Library**: `langchain_mcp_adapters` + `langgraph` (`create_react_agent`) + `traceloop-sdk` WITHOUT `should_enrich_metrics`. LangChain instrumented via Traceloop.
- **Provider**: Azure OpenAI (`azure_openai` via `init_chat_model`, deployment from `AZURE_OPENAI_DEPLOYMENT`)
- **OTel setup**: `setup_tracing("mcp-agent-demo")` called from `dynatrace.py`. `Traceloop.init(app_name="mcp-agent-demo", ...)` with `resource_attributes={"gen_ai.agent.name": "mcp-agent-demo", "service.name": "mcp-agent-demo", "service.version": "0.0.1"}`. **No `should_enrich_metrics=True`**. Endpoint from `OTEL_ENDPOINT` env var; token from `DT_API_TOKEN` env var or `/etc/secrets/dynatrace_otel` file.
- **MCP server**: TypeScript, OpenTelemetry SDK (`@opentelemetry/sdk-node`), raw span instrumentation on tool calls. Endpoint and token resolved identically via `OTEL_ENDPOINT` / `DT_API_TOKEN`.

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
| MCP tool spans | ⚠️ | MCP server emits raw OTel spans with `tool.name` / `mcp.method` attributes — visible in distributed trace view but not in AI Observability prompts table |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.client.operation.duration` | AR-025 | All latency charts empty |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost dashboard metric tiles show $0 — distinct from span token attributes AR-006/AR-007. Requires `should_enrich_metrics=True` or a custom MeterProvider. |
| `gen_ai.token.type` (metric dimension) | AR-024 | Cost dashboard shows no data |
| `gen_ai.agent.name` (as span attribute) | AR-010 | Agent quick filter empty; currently only on Resource |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping |
| `span.status_code` | AR-047 | If OTel SDK not properly wired, all requests appear successful; no error signal in health tile |

## What to fix in the example app

**1. Add `should_enrich_metrics=True` (fixes latency + cost charts)**

In `dynatrace.py`, change:

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

**2. `gen_ai.agent.name` — move from Resource to span attribute (fixes agent quick filter)**

After `Traceloop.init()` in `dynatrace.py`:

```python
from traceloop.sdk import Traceloop
Traceloop.set_association_properties({"gen_ai.agent.name": service_name})
```

**3. `gen_ai.conversation.id` — not emitted**

The demo runs a single-turn query. If extended to multi-turn, add conversation ID via Traceloop association properties before each agent invocation.

**4. MCP spans use custom attribute convention**

MCP tool call spans (from `langchain_mcp_adapters`) use `mcp.method.name` rather than `gen_ai.*` attributes. These are visible as child spans in the distributed trace view but will not appear in the AI Observability prompts table. This is by design.
