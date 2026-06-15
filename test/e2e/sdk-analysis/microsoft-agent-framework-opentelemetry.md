# Microsoft Agent Framework — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.1.1 | **Path**: `microsoft-agent-framework/opentelemetry/app.py` | **Profile**: azure (Azure OpenAI)

## Instrumentation

- **Library**: `agent-framework==1.8.1` (Microsoft Agent Framework) with native OTel GenAI instrumentation via `configure_otel_providers(enable_sensitive_data=True)`.
- **Provider**: Azure OpenAI (`OPENAI_API_BASE` = `https://travel-advisor-demo.openai.azure.com/...`, model `gpt-5.4-mini`, `OPENAI_API_VERSION=2025-04-01-preview`)
- **OTel setup**: MAF calls `configure_otel_providers(enable_sensitive_data=True)` internally. OTel endpoint from `DT_ENDPOINT` + `DT_API_TOKEN` env vars. Delta temporality set. Two span types per call: `invoke_agent` (outer, has `gen_ai.agent.name`, `gen_ai.request.temperature`) + `chat` (inner, has model, tokens, content). `gen_ai.conversation.id` available via `default_options`. Metrics: `gen_ai.client.operation.duration` + `gen_ai.client.token.usage` with delta temporality.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | MAF emits `gen_ai.system` = "openai" or `gen_ai.provider.name` (modern) via native OTel |
| `service.name` | ✅ | set via OTel resource configuration in MAF setup |
| `gen_ai.request.model` | ✅ | emitted on `chat` spans by MAF |
| `gen_ai.response.model` | ✅ | emitted on `chat` spans by MAF |
| `gen_ai.usage.input_tokens` | ✅ | MAF uses modern primary name `gen_ai.usage.input_tokens` |
| `gen_ai.usage.output_tokens` | ✅ | MAF uses modern primary name `gen_ai.usage.output_tokens` |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | All required fields present with modern attribute names |
| Prompts — content | ✅ | `enable_sensitive_data=True` enables content capture; emitted as span attributes on `chat` spans |
| Prompts — model column | ✅ | `gen_ai.request.model` present on `chat` spans |
| Latency charts | ✅ | MAF natively emits `gen_ai.client.operation.duration` histogram with delta temporality |
| Cost dashboard | ✅ | MAF natively emits `gen_ai.client.token.usage` with `gen_ai.token.type` dimension and delta temporality |
| Agent quick filter | ✅ | `gen_ai.agent.name` emitted on `invoke_agent` spans |
| Provider quick filter | ✅ | Provider identity attribute present |
| Guardrails (Azure) | ❌ | `gen_ai.prompt.prompt_filter_results` + `gen_ai.completion.content_filter_results` not emitted by MAF; Azure Content Safety not configured |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | N/A | Azure profile — not applicable |

## Note on two-span model

MAF emits two spans per agent invocation:
- `invoke_agent`: outer span with `gen_ai.agent.name`, `gen_ai.request.temperature`, conversation context — but **no model attributes**
- `chat`: inner span with `gen_ai.request.model`, `gen_ai.response.model`, token usage, content — but no agent name

This split means that `gen_ai.agent.name` and `gen_ai.request.model` never appear on the same span. DT's model comparison dashboard (which reads `gen_ai.request.temperature` alongside `gen_ai.request.model`) may not correlate these correctly if it requires both attributes on the same span.

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.prompt.prompt_filter_results` | Azure guardrail cards empty |
| `gen_ai.completion.content_filter_results` | Azure guardrail cards empty |
| `gen_ai.request.temperature` on `chat` spans | Model comparison dashboard may not correlate temperature with model (temperature is on `invoke_agent` span, model is on `chat` span) |

## What to fix in the example app

**1. Azure guardrail attributes — library limitation**

MAF does not emit `gen_ai.prompt.prompt_filter_results` or `gen_ai.completion.content_filter_results` even when Azure Content Safety is active. This is a library gap. No app-level fix without patching MAF or post-processing spans. Document this as a known limitation.

**2. Temperature + model correlation across spans**

`gen_ai.request.temperature` is set on the `invoke_agent` span and `gen_ai.request.model` is on the child `chat` span. If DT's model comparison requires both on the same span, add temperature to the `chat` span manually — but this depends on MAF's API surface:

```python
# If MAF allows custom attributes on the chat span:
chat_span.set_attribute("gen_ai.request.temperature", float(os.environ.get("TEMPERATURE", 0.7)))
```

Alternatively, document the span model so users know where to look for each attribute.

**3. `gen_ai.conversation.id` — verify `default_options` propagation**

MAF supports `gen_ai.conversation.id` via `default_options`. Confirm in `app.py` that it is passed consistently for multi-turn conversations. If the demo does not configure `default_options` with a conversation ID, threads will not group in DT's prompts view.

**4. `app.py` does not yet exist in repo**

At time of analysis, `microsoft-agent-framework/opentelemetry/app.py` has not been committed. The analysis above is based on the MAF framework's known OTel capabilities (version 1.8.1), the `.env` file present in the directory, and the prompt specification. Once `app.py` is written, re-validate these findings against the actual implementation.
