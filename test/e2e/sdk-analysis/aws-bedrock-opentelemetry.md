# AWS Bedrock + OTel Collector — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `aws-bedrock/opentelemetry/main.py` | **Profile**: bedrock | **Dashboard**: `bedrock.dashboard.json`

## Instrumentation

- **Library**: `opentelemetry-instrumentation-bedrock` (`BedrockInstrumentor`) + `opentelemetry-instrumentation-botocore` (`BotocoreInstrumentor`) + `traceloop-sdk` with `should_enrich_metrics=True`. Also: `RequestsInstrumentor`, `AsyncioInstrumentor`.
- **Provider**: AWS Bedrock (`boto3` client, `bedrock-runtime`, model `us.anthropic.claude-haiku-4-5-20251001-v1:0`)
- **OTel setup**: `Traceloop.init(app_name="bedrock_example_app", ..., should_enrich_metrics=True, disable_batch=True, api_endpoint="http://localhost:4318")`. Sends to a local OTel collector (not directly to DT). OTel logs pipeline configured. Traceloop `@workflow`, `@task`, `@agent` decorators used. Delta temporality set via env var.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | `gen_ai.system` = "aws.bedrock" or "bedrock" via BedrockInstrumentor / Traceloop |
| `service.name` | ✅ | set to "bedrock_example_app" via `Traceloop.init(app_name=...)` |
| `gen_ai.request.model` | ✅ | emitted by BedrockInstrumentor |
| `gen_ai.response.model` | ✅ | emitted by BedrockInstrumentor |
| `gen_ai.usage.input_tokens` | ⚠️ via fallback | emits `gen_ai.usage.prompt_tokens` (deprecated AR-026); DT accepts as fallback |
| `gen_ai.usage.output_tokens` | ⚠️ via fallback | emits `gen_ai.usage.completion_tokens` (deprecated AR-027); DT accepts as fallback |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + required fields all present (via fallbacks) |
| Prompts — content | ⚠️ legacy | `gen_ai.prompt.0.content` + `gen_ai.completion.0.content` via Traceloop/BedrockInstrumentor; DT falls back to these |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ✅ | `should_enrich_metrics=True` → `gen_ai.client.operation.duration` emitted |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.prompt_tokens` / `gen_ai.usage.completion_tokens` present on spans (AR-006/AR-007 via fallback) |
| Cost dashboard (metric) | ✅ | `should_enrich_metrics=True` → `gen_ai.client.token.usage` metric (AR-044) with `gen_ai.token.type` dimension emitted by Traceloop |
| Service health tile | ⚠️ | `span.status_code` (AR-047) emitted by OTel SDK automatically; health tile functional if OTel SDK is correctly wired |
| Agent quick filter | ❌ | `@agent("aws_bedrock_agent")` creates a Traceloop workflow/agent span but does not set `gen_ai.agent.name` as a span attribute on LLM child spans; agent quick filter may be empty |
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
| Agent quick filter | ❌ Empty | `gen_ai.agent.name` not propagated to LLM child spans |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.agent.name` (on LLM spans) | AR-010 | Agent quick filter empty; `@agent` decorator creates a workflow-level span, the agent name does not propagate down to individual `gen_ai.*` LLM spans as `gen_ai.agent.name` attribute |
| `gen_ai.bedrock.guardrail.*` | AR-017/AR-018/AR-019 | Bedrock guardrail cards empty (no guardrails configured) |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping |
| `gen_ai.client.token.usage` (metric, AR-044) | AR-044 | Note: this IS emitted via `should_enrich_metrics=True`. If the collector is down, metric pipeline breaks silently. Distinct from span token attributes AR-006/AR-007. |

## Dashboard gaps (Bedrock-specific)

The following attributes are expected from the Bedrock SDK and are in the baseline contract, but **no dashboard tile in `bedrock.dashboard.json` currently visualises them**. Their absence does not degrade any current dashboard — this is a dashboard gap, not a silent failure:

| Attribute | Rule ID | Note |
|-----------|---------|------|
| `gen_ai.bedrock.guardrail.topics` | AR-020 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |
| `gen_ai.bedrock.guardrail.words` | AR-021 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |

## What to fix in the example app

**1. `gen_ai.agent.name` not propagated to LLM spans**

Traceloop's `@agent` decorator creates a wrapper span named after the agent, but individual LLM call spans (from BedrockInstrumentor) don't inherit `gen_ai.agent.name` as a span attribute. DT's agent quick filter relies on this attribute being present on the spans directly.

Fix: explicitly set `gen_ai.agent.name` as an association property before calling the LLM, or set it on the outer agent span and rely on DT trace propagation. The most reliable approach with Traceloop is to add it to `Traceloop.set_association_properties()`:

```python
Traceloop.set_association_properties({
    "gen_ai.agent.name": "aws_bedrock_agent",
    # existing properties:
    "appid": "1234567890",
    ...
})
```

**2. OTel collector as intermediary — collector must be running**

The demo sends all telemetry to `http://localhost:4318`. If the collector is not running, no data reaches DT. This is by design but should be noted in docs. No code fix required.

**3. Bedrock guardrails — demo scope limitation**

No guardrail ID is configured. `guard_rail_metrics.py` reads CloudWatch metrics for a placeholder guardrail ID and is not wired into the main OTel pipeline. To populate DT guardrail cards, Bedrock guardrails would need to be created and the BedrockInstrumentor would need to emit `gen_ai.bedrock.guardrail.*` OTel attributes (vs. CloudWatch metrics).

**4. Infinite loop in `__main__`**

The script runs `run_agent()` in an infinite loop (up to 60 iterations). This is fine for demo/load generation but would fill DT with data rapidly in a real environment.
