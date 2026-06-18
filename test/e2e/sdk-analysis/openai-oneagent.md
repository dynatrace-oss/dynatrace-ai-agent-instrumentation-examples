# OpenAI OneAgent — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `openai/oneagent/app.py` | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `openai` SDK (`openai >= 2.38.0`, `openai.OpenAI` client) — bare SDK, no application-level OTel or Traceloop configuration.
- **Provider**: OpenAI (or Azure OpenAI depending on env vars — `OPENAI_API_BASE` / `OPENAI_API_VERSION` select Azure-compatible mode). Default model: `gpt-4o`.
- **OTel setup**: No application-level OTel. The app is a minimal FastAPI service. Instrumentation is provided entirely by Dynatrace OneAgent injected at the pod level.
  - OneAgent auto-instruments the OpenAI Python SDK via the fully supported **Python OpenAI** sensor. This is not experimental — it is a production-grade sensor that gates all OpenAI AI monitoring.
  - The optional **Python OpenAI prompt capture** feature must be enabled separately to populate `gen_ai.input.messages` / `gen_ai.output.messages` in the prompts view.
  - The **Python FastAPI** sensor must be enabled to generate HTTP entry-point spans.
  - The app uses `stream=True`. OneAgent captures span attributes when the request starts (model, provider identity), but response token counts and response model from the streaming response depend on OneAgent's streaming support. Core attributes are captured; `gen_ai.response.model` and exact token counts may vary under streaming versus non-streaming.
  - There is no `gen_ai.*` span attribute emission from the app code itself.

> **Note**: `openai/openinference/app.py` is a separate demo covered by `openai-openinference.md`. This file covers only the oneagent variant.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | Python OpenAI sensor (fully supported) emits provider identity |
| `service.name` | ✅ | Set by OneAgent from K8s/process metadata |
| `gen_ai.request.model` | ✅ | Captured by Python OpenAI sensor at span start |
| `gen_ai.response.model` | ⚠️ | May be limited under streaming; fully captured in non-streaming mode |
| `gen_ai.usage.input_tokens` | ⚠️ | May be limited under streaming; confirmed in non-streaming mode |
| `gen_ai.usage.output_tokens` | ⚠️ | May be limited under streaming; confirmed in non-streaming mode |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity present via Python OpenAI sensor |
| Prompts — content | ⚠️ optional | Available when "Python OpenAI prompt capture" feature is enabled; streaming may limit capture |
| Prompts — model column | ✅ | `gen_ai.request.model` captured by Python OpenAI sensor |
| Latency charts | ❌ | OneAgent does not emit `gen_ai.client.operation.duration` OTel metric |
| Cost dashboard (span tokens) | ⚠️ | Token counts depend on streaming capture |
| Cost dashboard (metric) | ❌ | `gen_ai.client.token.usage` OTel metric not emitted by OneAgent |
| Service health tile | ✅ | Python FastAPI sensor captures HTTP spans with status codes |
| Agent quick filter | N/A | Direct OpenAI SDK — no agent framework |
| Provider quick filter | ✅ | Provider identity present |
| Guardrails (Azure) | ⚠️ | Possible if using Azure via `OPENAI_API_BASE`, but AR-015/AR-016 not emitted without Azure Content Safety configuration |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | ❌ | Prompt caching not used in this demo |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Root cause |
|-----------|-----------|
| `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | Streaming may limit capture — consider switching to non-streaming |
| `gen_ai.input.messages` / `gen_ai.output.messages` | Requires enabling "Python OpenAI prompt capture" optional feature |
| `gen_ai.client.operation.duration` | OneAgent does not emit this OTel metric |
| `gen_ai.client.token.usage` (metric) | OneAgent does not emit this OTel metric |

## What to fix

**1. Enable Python OpenAI sensor** in Settings → OneAgent features. This is a fully supported sensor (not experimental). Restart the Python process after enabling.

**2. Enable Python OpenAI prompt capture** (optional) to populate `gen_ai.input.messages` / `gen_ai.output.messages` and show content in the prompts view.

**3. Enable Python FastAPI sensor** to generate HTTP entry-point spans for the service health tile.

**4. Consider switching from `stream=True` to non-streaming** for more complete attribute capture (`gen_ai.response.model`, token counts). The streaming loop in this demo assembles all chunks synchronously anyway, so non-streaming provides the same end-result with better observability coverage:

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "Write a haiku."}],
    max_completion_tokens=20,
    stream=False,
)
return response.choices[0].message.content or ""
```

**5. OTel metrics (latency charts, cost dashboard)**: Not emitted by OneAgent. Add a separate OTel metrics pipeline if latency charts (`gen_ai.client.operation.duration`) or cost dashboard metrics (`gen_ai.client.token.usage`) are required.

**6. Azure mode (via `OPENAI_API_BASE`)**: If targeting Azure OpenAI, Azure Content Safety (AR-015/AR-016) still requires explicit configuration to populate guardrail views.
