# AWS Bedrock + OTel Collector — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.1.1 | **Path**: `aws-bedrock/opentelemetry/main.py` | **Profile**: bedrock

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
| Cost dashboard | ✅ | `should_enrich_metrics=True` → `gen_ai.client.token.usage` with `gen_ai.token.type` |
| Agent quick filter | ❌ | `@agent("aws_bedrock_agent")` creates a Traceloop workflow/agent span but does not set `gen_ai.agent.name` as a span attribute on LLM child spans; agent quick filter may be empty |
| Provider quick filter | ✅ | `gen_ai.system` present |
| Guardrails (Azure) | N/A | Not Azure |
| Guardrails (Bedrock) | ❌ | No guardrails configured; `gen_ai.bedrock.guardrail.*` attributes not emitted |
| Cache hit rate (OpenAI) | N/A | Not OpenAI |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.agent.name` (on LLM spans) | Agent quick filter empty; `@agent` decorator creates a workflow-level span, the agent name does not propagate down to individual `gen_ai.*` LLM spans as `gen_ai.agent.name` attribute |
| `gen_ai.bedrock.guardrail.*` | Bedrock guardrail cards empty (no guardrails configured) |
| `gen_ai.conversation.id` | No conversation thread grouping |

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
