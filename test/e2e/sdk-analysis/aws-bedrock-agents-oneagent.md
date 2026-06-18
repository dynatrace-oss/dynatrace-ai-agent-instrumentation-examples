# AWS Bedrock Agents (LangGraph + LangChain) — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `aws-bedrock-agents/oneagent/main.py` + `travel_agent.py` | **Profile**: bedrock | **Dashboard**: `bedrock.dashboard.json`

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
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens` present on spans (AR-006/AR-007 via fallback) |
| Cost dashboard (metric) | ✅ | `should_enrich_metrics=True` → `gen_ai.client.token.usage` metric (AR-044) with `gen_ai.token.type` dimension emitted by Traceloop |
| Service health tile | ✅ | `span.status_code` (AR-047) auto-emitted by OTel SDK |
| Agent quick filter | ✅ | LangGraph graph name captured as agent name by Traceloop's LangChain instrumentor |
| Provider quick filter | ✅ | `gen_ai.system` present |
| Guardrails (Azure) | N/A | Not Azure |
| Guardrails (Bedrock) | ❌ | No guardrails configured; `gen_ai.bedrock.guardrail.*` attributes not emitted |
| Cache hit rate (OpenAI) | N/A | Not OpenAI |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ⚠️ Legacy content | Modern `gen_ai.input.messages` / `gen_ai.output.messages` missing; falls back to deprecated attributes |
| Latency charts (p99/mean) | ✅ Yes | — |
| Cost dashboard tiles | ✅ Yes | `gen_ai.client.token.usage` metric present via `should_enrich_metrics=True` |
| Service health tile | ✅ Yes | `span.status_code` auto-emitted by OTel SDK |
| Guardrail cards (Bedrock) | ❌ Empty | `gen_ai.bedrock.guardrail.activation` (AR-017), `gen_ai.bedrock.guardrail.content` (AR-018), `gen_ai.bedrock.guardrail.sensitive_info` (AR-019) not emitted |
| Bedrock cache tiles | ❌ Empty | `gen_ai.prompt.caching` metric (AR-045) not emitted; no Bedrock prompt caching configured |
| Agent quick filter | ✅ Yes | LangGraph graph name captured as `gen_ai.agent.name` |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.bedrock.guardrail.*` | AR-017/AR-018/AR-019 | Bedrock guardrail cards empty (no guardrails configured in demo) |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping; `session_id` passed in `agent_invocation()` not propagated to spans |
| `gen_ai.client.token.usage` (metric, AR-044) | AR-044 | Note: this IS emitted via `should_enrich_metrics=True`. Distinct from span token attributes AR-006/AR-007 — requires the metrics pipeline to be active. |

## Dashboard gaps (Bedrock-specific)

The following attributes are expected from the Bedrock SDK and are in the baseline contract, but **no dashboard tile in `bedrock.dashboard.json` currently visualises them**. Their absence does not degrade any current dashboard — this is a dashboard gap, not a silent failure:

| Attribute | Rule ID | Note |
|-----------|---------|------|
| `gen_ai.bedrock.guardrail.topics` | AR-020 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |
| `gen_ai.bedrock.guardrail.words` | AR-021 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |

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
