# AWS Strands SDK — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `aws-strands/oneagent/main.py` | **Profile**: bedrock | **Dashboard**: `bedrock.dashboard.json`

## Instrumentation

- **Library**: `strands` SDK (native OTel, no Traceloop). `URLLib3Instrumentor` also applied.
- **Provider**: AWS Bedrock (`BedrockModel`, model `anthropic.claude-3-7-sonnet-20250219-v1:0`)
- **OTel setup**: Custom `TracerProvider` + `MeterProvider` in `aws-strands/oneagent/dynatrace.py` (`init()` called at top of `main.py`). Direct OTLP HTTP export to DT. `SimpleSpanProcessor` for traces, `PeriodicExportingMetricReader` for metrics. Resource: `service.name=aws-agent-sdk`. No Traceloop involved.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | Strands emits `gen_ai.system` (value depends on Strands version; typically "aws.bedrock" or Bedrock provider string) |
| `service.name` | ✅ | set to "aws-agent-sdk" in `dynatrace.py` Resource |
| `gen_ai.request.model` | ✅ | Strands emits modern `gen_ai.request.model` |
| `gen_ai.response.model` | ✅ | Strands emits modern `gen_ai.response.model` |
| `gen_ai.usage.input_tokens` | ✅ | Strands uses modern primary name `gen_ai.usage.input_tokens` |
| `gen_ai.usage.output_tokens` | ✅ | Strands uses modern primary name `gen_ai.usage.output_tokens` |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | All required fields present with modern names |
| Prompts — content | ❌ | Strands emits content as span events (`gen_ai.user.message`, `gen_ai.assistant.message`); DT reads `gen_ai.input.messages`/`gen_ai.output.messages` as span attributes, not events |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ✅ | Strands SDK natively emits `gen_ai.client.operation.duration` metric; metrics pipeline configured in `dynatrace.py` |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` present on spans |
| Cost dashboard (metric) | ✅ | Strands natively emits `gen_ai.client.token.usage` metric (AR-044) with `gen_ai.token.type` dimension |
| Service health tile | ✅ | `span.status_code` (AR-047) auto-emitted by OTel SDK |
| Agent quick filter | ✅ | Strands emits agent spans with `gen_ai.agent.name` |
| Provider quick filter | ✅ | `gen_ai.system` present |
| Guardrails (Azure) | N/A | Not Azure |
| Guardrails (Bedrock) | ❌ | No Bedrock guardrails configured; `gen_ai.bedrock.guardrail.*` attributes not emitted |
| Cache hit rate (OpenAI) | N/A | Not OpenAI |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ❌ Empty | Content emitted as span events, not span attributes; DT prompts table requires span attributes `gen_ai.input.messages` / `gen_ai.output.messages` |
| Latency charts (p99/mean) | ✅ Yes | — |
| Cost dashboard tiles | ✅ Yes | `gen_ai.client.token.usage` metric natively emitted by Strands SDK |
| Service health tile | ✅ Yes | `span.status_code` auto-emitted by OTel SDK |
| Guardrail cards (Bedrock) | ❌ Empty | `gen_ai.bedrock.guardrail.activation` (AR-017), `gen_ai.bedrock.guardrail.content` (AR-018), `gen_ai.bedrock.guardrail.sensitive_info` (AR-019) not emitted |
| Bedrock cache tiles | ❌ Empty | `gen_ai.prompt.caching` metric (AR-045) not emitted; no Bedrock prompt caching configured |
| Agent quick filter | ✅ Yes | `gen_ai.agent.name` emitted by Strands |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.input.messages` / `gen_ai.output.messages` (as span attributes) | AR-011/AR-012 | Prompts table content is empty; Strands emits these as span events, which DT does not currently read for the prompts table |
| `gen_ai.bedrock.guardrail.*` | AR-017/AR-018/AR-019 | Bedrock guardrail cards empty (no guardrails configured) |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping |

## Dashboard gaps (Bedrock-specific)

The following attributes are expected from the Bedrock SDK and are in the baseline contract, but **no dashboard tile in `bedrock.dashboard.json` currently visualises them**. Their absence does not degrade any current dashboard — this is a dashboard gap, not a silent failure:

| Attribute | Rule ID | Note |
|-----------|---------|------|
| `gen_ai.bedrock.guardrail.topics` | AR-020 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |
| `gen_ai.bedrock.guardrail.words` | AR-021 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |

## What to fix in the example app

**1. Prompts table content — span events vs. span attributes (library limitation)**

Strands SDK emits prompt/completion content as OpenTelemetry span events following the GenAI Events spec. Dynatrace's AI Observability prompts table currently reads `gen_ai.input.messages` and `gen_ai.output.messages` as span attributes. There is no workaround at the `main.py` level — this is a Strands SDK behaviour and a DT ingestion gap. No code change in the example app can fix this without patching the library or post-processing spans via a collector transform.

**2. Bedrock guardrails — not configured**

To populate guardrail cards, the Bedrock model would need to be configured with a guardrail ID, and Strands/BedrockInstrumentor would need to emit `gen_ai.bedrock.guardrail.*` attributes. This is a demo scope limitation, not a code bug.

**3. `gen_ai.conversation.id` — not emitted**

Strands does not automatically assign conversation IDs. Fix: manually set `gen_ai.conversation.id` on the outer span created in `main.py`:

```python
with trace.get_tracer("strands-agents.tracer").start_as_current_span(
    name="/api", kind=trace.SpanKind.SERVER
) as span:
    span.set_attribute("gen_ai.conversation.id", "some-session-id")
    main()
```

**4. `service.name` hardcoded in `dynatrace.py`**

`aws-agent-sdk` is hardcoded. Consider making it configurable via environment variable for reuse in different deployment contexts.
