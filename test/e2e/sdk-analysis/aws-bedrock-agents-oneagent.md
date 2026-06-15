# AWS Bedrock Agents (LangGraph + LangChain) — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.1.1 | **Path**: `aws-bedrock-agents/oneagent/main.py` + `travel_agent.py` | **Profile**: bedrock

## Instrumentation

- **Library**: `langchain` + `langchain_core` + `langgraph` + `traceloop-sdk` with `should_enrich_metrics=True`. LangSmith OTel bridge also active (`LANGSMITH_OTEL_ENABLED=true`).
- **Provider**: AWS Bedrock Converse API (`init_chat_model(..., model_provider="bedrock_converse")`), model `eu.anthropic.claude-3-7-sonnet-20250219-v1:0`
- **OTel setup**: `Traceloop.init(app_name="agent-core-samples", ..., should_enrich_metrics=True, disable_batch=True)` in `dynatrace.py`. Endpoint read from `OTEL_ENDPOINT` env var (defaults to a hardcoded DT tenant URL). `LANGSMITH_OTEL_ENABLED=true` in `travel_agent.py` produces additional LangSmith-format spans alongside Traceloop spans.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | via `gen_ai.system` = "aws.bedrock" or "anthropic" (Traceloop LangChain instrumentor) |
| `service.name` | ✅ | set to "agent-core-samples" via `Traceloop.init(app_name=...)` |
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
| Latency charts | ✅ | `should_enrich_metrics=True` → `gen_ai.client.operation.duration` emitted |
| Cost dashboard | ✅ | `should_enrich_metrics=True` → `gen_ai.client.token.usage` with `gen_ai.token.type` |
| Agent quick filter | ✅ | LangGraph graph name captured as agent name by Traceloop's LangChain instrumentor |
| Provider quick filter | ✅ | `gen_ai.system` present |
| Guardrails (Azure) | N/A | Not Azure |
| Guardrails (Bedrock) | ❌ | No guardrails configured; `gen_ai.bedrock.guardrail.*` attributes not emitted |
| Cache hit rate (OpenAI) | N/A | Not OpenAI |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.bedrock.guardrail.*` | Bedrock guardrail cards empty (no guardrails configured in demo) |
| `gen_ai.conversation.id` | No conversation thread grouping; `session_id` passed in `agent_invocation()` not propagated to spans |

## What to fix in the example app

**1. Hardcoded DT endpoint in `dynatrace.py`**

The fallback value in `dynatrace.py` is hardcoded to `https://wkf10640.live.dynatrace.com/api/v2/otlp`. This works for deployment but is not portable. Fix: remove the hardcoded default and require `OTEL_ENDPOINT` to be set in the environment (or document it clearly in README):

```python
OTEL_ENDPOINT = os.environ["OTEL_ENDPOINT"]  # fail fast if not set
```

**2. `gen_ai.conversation.id` — propagate session ID to spans**

`session_id` is passed to `agent_invocation()` in `travel_agent.py` but never surfaces as a span attribute. Fix: set it via Traceloop association properties before each invocation:

```python
from traceloop.sdk import Traceloop
Traceloop.set_association_properties({"gen_ai.conversation.id": session_id})
result = graph.invoke(tmp_msg, config=config)
```

**3. `LANGSMITH_OTEL_ENABLED=true` — potential span duplication**

Setting `LANGSMITH_OTEL_ENABLED=true` in `travel_agent.py` causes LangSmith to emit additional spans via its own OTel bridge. Combined with Traceloop, this can produce duplicate or overlapping spans in DT. If LangSmith tracing is not required, remove this env var or set it to `false`.

**4. Bedrock guardrails — demo scope limitation**

No Bedrock guardrail is configured in the demo. Enabling `gen_ai.bedrock.guardrail.*` attributes would require adding a guardrail to the Bedrock model configuration and verifying that Traceloop's BedrockInstrumentor (if present) or LangChain's Bedrock integration emits those fields.

**5. Token attribute names — library limitation**

Traceloop emits legacy token names. DT accepts them as fallbacks. No action required for functional correctness.
