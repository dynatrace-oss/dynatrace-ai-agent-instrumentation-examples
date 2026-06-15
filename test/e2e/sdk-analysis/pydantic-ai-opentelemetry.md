# Pydantic AI — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.1.1 | **Path**: `pydantic-ai/opentelemetry/backend/main.py` + `otel_setup.py` | **Profile**: azure + bedrock (randomly selected per request)

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
| Cost dashboard | ✅ | pydantic-ai natively emits `gen_ai.client.token.usage` with `gen_ai.token.type` dimension |
| Agent quick filter | ⚠️ | `gen_ai.agent.name` set on Resource only (not as per-span attribute); agent quick filter may not work — DT reads span attribute |
| Provider quick filter | ✅ | `gen_ai.provider.name` present |
| Guardrails (Azure) | ❌ | `gen_ai.prompt.prompt_filter_results` + `gen_ai.completion.content_filter_results` not emitted |
| Guardrails (Bedrock) | ❌ | `gen_ai.bedrock.guardrail.*` not emitted; no guardrails configured |
| Cache hit rate (OpenAI) | N/A | Azure + Bedrock only — not applicable |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.input.messages` / `gen_ai.output.messages` (as span attributes) | Prompts table content empty — content is in span events, which DT does not use for prompts table |
| `gen_ai.agent.name` (as per-span attribute) | Agent quick filter may not work; only set on Resource |
| `gen_ai.prompt.prompt_filter_results` | Azure guardrail cards empty |
| `gen_ai.completion.content_filter_results` | Azure guardrail cards empty |
| `gen_ai.bedrock.guardrail.*` | Bedrock guardrail cards empty |
| `gen_ai.conversation.id` | No conversation thread grouping |
| `gen_ai.system_instructions` | System prompt column empty in prompts table |

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
