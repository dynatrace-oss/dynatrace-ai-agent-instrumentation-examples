# Pydantic AI — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `pydantic-ai/opentelemetry/backend/main.py` + `otel_setup.py` | **Profile**: azure + bedrock (randomly selected per request) | **Dashboard**: `azureai.dashboard.json` (primary) / `bedrock.dashboard.json` (secondary)

## Instrumentation

- **Library**: `pydantic-ai` with `InstrumentationSettings(tracer_provider=..., meter_provider=..., include_content=True)`. Native OTel GenAI semconv instrumentation — no Traceloop.
- **Provider**: Azure OpenAI (`AzureProvider`) OR AWS Bedrock (`BedrockConverseModel`) — randomly selected per `/api/ask` request from three builders: `build_azure_model`, `build_bedrock_sonnet`, `build_bedrock_haiku`.
- **OTel setup**: `setup_otel("pydantic-ai-music-agent")` in `otel_setup.py`. Manual `TracerProvider` + `MeterProvider` with OTLP HTTP exporters to DT. Resource includes `gen_ai.agent.name: pydantic-ai-music-agent`. Delta temporality set. DT endpoint from `DT-ENDPOINT` + `DT-TOKEN` env vars.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | pydantic-ai emits `gen_ai.provider.name` (modern, not deprecated `gen_ai.system`) |
| `service.name` | ✅ | set to "pydantic-ai-music-agent" via Resource |
| `gen_ai.request.model` | ✅ | emitted by pydantic-ai instrumentation |
| `gen_ai.response.model` | ✅ | emitted by pydantic-ai instrumentation |
| `gen_ai.usage.input_tokens` | ✅ | pydantic-ai uses modern primary name `gen_ai.usage.input_tokens` |
| `gen_ai.usage.output_tokens` | ✅ | pydantic-ai uses modern primary name `gen_ai.usage.output_tokens` |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | All required fields present with modern names |
| Prompts — content | ❌ | pydantic-ai with `include_content=True` emits content as span **events** (`gen_ai.user.message`, `gen_ai.assistant.message`); DT reads `gen_ai.input.messages` / `gen_ai.output.messages` as span **attributes** — not events. Prompts table is empty. |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ✅ | pydantic-ai natively emits `gen_ai.client.operation.duration` metric; `MeterProvider` configured |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` present on spans |
| Cost dashboard (metric) | ✅ | pydantic-ai natively emits `gen_ai.client.token.usage` metric (AR-044) with `gen_ai.token.type` dimension |
| Service health tile | ✅ | `span.status_code` (AR-047) auto-emitted by OTel SDK |
| Agent quick filter | ⚠️ | `gen_ai.agent.name` set on Resource only (not as per-span attribute); agent quick filter may not work — DT reads span attribute |
| Provider quick filter | ✅ | `gen_ai.provider.name` present |
| Guardrails (Azure) | ❌ | `gen_ai.prompt.prompt_filter_results` + `gen_ai.completion.content_filter_results` not emitted |
| Guardrails (Bedrock) | ❌ | `gen_ai.bedrock.guardrail.*` not emitted; no guardrails configured |
| Cache hit rate (OpenAI) | N/A | Azure + Bedrock only — not applicable |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ❌ Empty | Content emitted as span events, not span attributes; DT requires `gen_ai.input.messages` / `gen_ai.output.messages` as span attributes |
| Latency charts (p99/mean) | ✅ Yes | `gen_ai.client.operation.duration` natively emitted |
| Cost dashboard tiles | ✅ Yes | `gen_ai.client.token.usage` metric (AR-044) natively emitted with `gen_ai.token.type` |
| Service health tile | ✅ Yes | `span.status_code` (AR-047) auto-emitted by OTel SDK |
| Azure guardrail cards | ❌ Empty | `gen_ai.prompt.prompt_filter_results` (AR-015) and `gen_ai.completion.content_filter_results` (AR-016) not emitted |
| Bedrock guardrail cards | ❌ Empty | `gen_ai.bedrock.guardrail.activation` (AR-017), `gen_ai.bedrock.guardrail.content` (AR-018), `gen_ai.bedrock.guardrail.sensitive_info` (AR-019) not emitted |
| Bedrock cache tiles | ❌ Empty | `gen_ai.prompt.caching` metric (AR-045) not emitted |
| Agent quick filter | ⚠️ Partial | `gen_ai.agent.name` set on Resource only, not per span; may not work for span-level filter |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.input.messages` / `gen_ai.output.messages` (as span attributes) | AR-011/AR-012 | Prompts table content empty — content is in span events, which DT does not use for prompts table |
| `gen_ai.agent.name` (as per-span attribute) | AR-010 | Agent quick filter may not work; only set on Resource |
| `gen_ai.prompt.prompt_filter_results` | AR-015 | Azure guardrail cards empty |
| `gen_ai.completion.content_filter_results` | AR-016 | Azure guardrail cards empty |
| `gen_ai.bedrock.guardrail.*` | AR-017/AR-018/AR-019 | Bedrock guardrail cards empty |
| `gen_ai.conversation.id` | AR-041 | No conversation thread grouping |
| `gen_ai.system_instructions` | AR-043 | System prompt column empty in prompts table |

## Dashboard gaps (Bedrock-specific)

The following attributes are expected from the Bedrock SDK and are in the baseline contract, but **no dashboard tile in `bedrock.dashboard.json` currently visualises them**. Their absence does not degrade any current dashboard — this is a dashboard gap, not a silent failure:

| Attribute | Rule ID | Note |
|-----------|---------|------|
| `gen_ai.bedrock.guardrail.topics` | AR-020 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |
| `gen_ai.bedrock.guardrail.words` | AR-021 | Expected from Bedrock SDK; not yet visualised in bedrock.dashboard.json |

## What to fix in the example app

**1. Prompts table content — span events vs. span attributes (library limitation + DT gap)**

`include_content=True` in `InstrumentationSettings` causes pydantic-ai to emit content as OTel span events per the GenAI Events spec. DT AI Observability currently reads `gen_ai.input.messages` / `gen_ai.output.messages` as span attributes. This is a library/platform mismatch.

Workaround: manually copy the content to span attributes on the outer `music_agent.ask` span in `main.py`:

```python
span.set_attribute("gen_ai.input.messages", str(request.question))
# After result:
span.set_attribute("gen_ai.output.messages", str(answer))
```

This duplicates content but ensures the prompts table populates until DT adds span event support.

**2. `gen_ai.agent.name` — add as per-span attribute (fixes agent quick filter)**

In `main.py`, within the `music_agent.ask` span:

```python
span.set_attribute("gen_ai.agent.name", "pydantic-ai-music-agent")
```

**3. `gen_ai.system_instructions` — add system prompt to span**

```python
span.set_attribute("gen_ai.system_instructions", MUSIC_SYSTEM_PROMPT)
```

**4. `gen_ai.conversation.id` — not applicable for stateless REST API**

Each `/api/ask` call is independent. If conversation tracking is added, propagate a session/conversation ID via span attribute.

**5. Azure + Bedrock guardrail attributes — library limitation**

Neither pydantic-ai's Azure provider nor Bedrock provider emits guardrail-specific OTel attributes. No app-level fix without patching the library.

**6. `DT-ENDPOINT` and `DT-TOKEN` env var names**

These use hyphens, which is unusual for env vars (most tools use underscores). Not a bug, but worth standardising to `DT_ENDPOINT` and `DT_TOKEN` to match other demos.
