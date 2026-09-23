# OpenAI OneAgent — Baseline Analysis

> *Baseline*: sdk-comparison-baseline.json v1.6.0 | *Path*: `openai/oneagent/app.py` | *Profile*: openai + oneagent-openai-guardrail | *Dashboard*: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `openai` SDK (`openai >= 2.38.0`, `openai.OpenAI` client) — bare SDK, no application-level OTel or Traceloop configuration.
- **Provider**: OpenAI (or Azure OpenAI depending on env vars — `OPENAI_API_BASE` / `OPENAI_API_VERSION` select Azure-compatible mode). Default model: `gpt-4o`.
- **OTel setup**: No application-level OTel. The app is a minimal FastAPI service. Instrumentation is provided entirely by Dynatrace OneAgent injected at the pod level.
  - OneAgent auto-instruments the OpenAI Python SDK via the fully supported **Python OpenAI** sensor. This is not experimental — it is a production-grade sensor that gates all OpenAI AI monitoring.
  - The optional **Python OpenAI prompt capture** feature must be enabled separately to populate `gen_ai.input.messages` / `gen_ai.output.messages` in the prompts view. This is necessary but not sufficient: the sensor does not reassemble streamed chunks, so under `stream=True` the output message is absent even with prompt capture enabled.
  - The **Python FastAPI** sensor must be enabled to generate HTTP entry-point spans.
  - The app uses non-streaming (`client.chat.completions.create` without `stream=True`), which returns a complete `ChatCompletion` object so OneAgent can capture `gen_ai.response.model` and token counts from the response body.
  - There is no `gen_ai.*` span attribute emission from the app code itself.

> **Note**: `openai/openinference/app.py` is a separate demo covered by `openai-openinference.md`. This file covers only the oneagent variant.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | Python OpenAI sensor (fully supported) emits provider identity |
| `service.name` | ✅ | Set by OneAgent from K8s/process metadata |
| `gen_ai.request.model` | ✅ | Captured by Python OpenAI sensor at span start |
| `gen_ai.response.model` | ✅ | Captured from the non-streaming response body |
| `gen_ai.usage.input_tokens` | ✅ | Captured from the non-streaming response body |
| `gen_ai.usage.output_tokens` | ✅ | Captured from the non-streaming response body |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity present via Python OpenAI sensor |
| Prompts — content | ⚠️ optional | Requires "Python OpenAI prompt capture" enabled **and** non-streaming; streaming drops the output message |
| Prompts — model column | ✅ | `gen_ai.request.model` captured by Python OpenAI sensor |
| Latency charts | ❌ | OneAgent does not emit `gen_ai.client.operation.duration` OTel metric |
| Cost dashboard (span tokens) | ✅ | Token counts captured from the non-streaming response body |
| Cost dashboard (metric) | ❌ | `gen_ai.client.token.usage` OTel metric not emitted by OneAgent |
| Service health tile | ✅ | Python FastAPI sensor captures HTTP spans with status codes |
| Agent quick filter | N/A | Direct OpenAI SDK — no agent framework |
| Provider quick filter | ✅ | Provider identity present |
| Guardrails (Azure) | ✅ conditional | Covered by `POST /haiku-guardrail`. OneAgent does *not* emit AR-015/AR-016 on its own spans — it normalizes Azure's content-filter payload into `gen_ai.guardrail.*` instead (AR-058, AR-062..AR-065). Requires Azure via `OPENAI_API_BASE`/`OPENAI_API_VERSION`, the `captureGuardrails` OneAgent feature enabled, and a filter that actually fires |
| Guardrails (Bedrock) | N/A | Not Bedrock. `gen_ai.bedrock.guardrail.*` (AR-017..AR-019) can never appear on this demo |
| Cache hit rate (OpenAI) | ❌ | Prompt caching not used in this demo |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Root cause |
|-----------|-----------|
| `gen_ai.input.messages` / `gen_ai.output.messages` | Requires "Python OpenAI prompt capture" enabled **and** non-streaming — under `stream=True` the sensor never sees an assembled response |
| `gen_ai.client.operation.duration` | OneAgent does not emit this OTel metric |
| `gen_ai.client.token.usage` (metric) | OneAgent does not emit this OTel metric |

## What to fix

**1. Enable Python OpenAI sensor** in Settings → OneAgent features. This is a fully supported sensor (not experimental). Restart the Python process after enabling.

**2. Enable Python OpenAI prompt capture** (optional) to populate `gen_ai.input.messages` / `gen_ai.output.messages` and show content in the prompts view. Note this only takes effect in non-streaming mode — see item 4.

**3. Enable Python FastAPI sensor** to generate HTTP entry-point spans for the service health tile.

**4. Non-streaming mode** is already used by this demo, and is required for message content. Observed on a tenant with prompt capture enabled: under `stream=True` the output message was absent from the span; switching to non-streaming made it appear. `gen_ai.response.model` and token counts are likewise read from the complete response body.

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "Write a haiku."}],
    max_completion_tokens=2000,
)
return response.choices[0].message.content or ""
```

Keep `max_completion_tokens` high enough for the model to finish its answer — too low a cap truncates the completion mid-sentence and the truncated text is what lands in `gen_ai.output.messages`.

**5. OTel metrics (latency charts, cost dashboard)**: Not emitted by OneAgent. Add a separate OTel metrics pipeline if latency charts (`gen_ai.client.operation.duration`) or cost dashboard metrics (`gen_ai.client.token.usage`) are required.

**6. Azure mode (via `OPENAI_API_BASE`)**: If targeting Azure OpenAI, Azure Content Safety (AR-015/AR-016) still requires explicit configuration to populate guardrail views.

*6. Guardrails (Azure mode via `OPENAI_API_BASE`)*: OneAgent's Python OpenAI sensor has an opt-in guardrail path, gated by the GenAI `captureGuardrails` feature (off by default). When enabled it parses Azure's `prompt_filter_results`, the per-choice `content_filter_results`, and the body of the `BadRequestError` Azure raises on a filtered prompt, and writes its own namespace:

| Attribute | Rule ID | Notes |
|-----------|---------|-------|
| `gen_ai.guardrail.input.content` | AR-058 | Record array, one entry per triggered prompt category: `{"type":"JAILBREAK"}`, `{"type":"HATE","confidence":"MEDIUM"}` |
| `gen_ai.guardrail.output.content` | AR-062 | Same, for the completion |
| `gen_ai.guardrail.input.words.lists` | AR-063 | Matched custom blocklist names (needs a blocklist configured) |
| `gen_ai.guardrail.output.words.lists` | AR-064 | Same, output side |
| `gen_ai.guardrail.output.sensitive_information.piis` | AR-065 | PII sub-categories in the completion; Azure has no input-side PII filter |

It never emits AR-015/AR-016 (`gen_ai.prompt.prompt_filter_results` / `gen_ai.completion.content_filter_results`) — those names belong to the OTel/OpenInference path only, which is why PPX's `gen_ai.guardrail.activation` metric never fired for OneAgent Azure traffic until AI-497. It also never emits the Bedrock-scoped `gen_ai.bedrock.guardrail.*` attributes, and no `gen_ai.guardrail.id`/`.version`: an Azure content filter is deployment configuration, not an addressable guardrail resource.

Only a request the filter intervened on carries any of this; a passing request carries nothing. The e2e suite therefore audits it as its own report (`openai-oneagent-guardrail`) against its own anchor span, and skips rather than fails when the filter did not fire.
