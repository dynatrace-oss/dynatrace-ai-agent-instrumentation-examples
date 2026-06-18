# Mistral AI — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `mistral/oneagent/app.py` | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `mistralai` SDK (`Mistral.chat.complete()`) — bare SDK, no OTel auto-instrumentation in application code.
- **Provider**: Mistral AI (`mistral-small-latest` model)
- **OTel setup**: No application-level OTel. Dynatrace OneAgent auto-instruments via the experimental **Mistral AI** sensor (Settings → OneAgent features → search "Mistral"). Also enable **Python FastAPI** sensor for HTTP entry-point spans. Experimental sensors are best-effort; not covered by DT support SLAs.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ expected | OneAgent experimental Mistral AI sensor emits provider identity |
| `service.name` | ✅ | Set by OneAgent from K8s/process metadata |
| `gen_ai.request.model` | ✅ expected | Captured by experimental Mistral AI sensor (best-effort) |
| `gen_ai.response.model` | ✅ expected | Captured by experimental Mistral AI sensor (best-effort) |
| `gen_ai.usage.input_tokens` | ✅ expected | Captured by experimental Mistral AI sensor (best-effort) |
| `gen_ai.usage.output_tokens` | ✅ expected | Captured by experimental Mistral AI sensor (best-effort) |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity expected from experimental Mistral AI sensor |
| Prompts — content | ❌ | Prompt capture (`gen_ai.input.messages` / `gen_ai.output.messages`) not available for experimental sensors; supported only for OpenAI and Bedrock |
| Prompts — model column | ✅ | `gen_ai.request.model` expected from experimental Mistral AI sensor |
| Latency charts | ❌ | OneAgent does not emit `gen_ai.client.operation.duration` OTel metric |
| Cost dashboard (span tokens) | ✅ expected | Token counts on spans expected from experimental Mistral AI sensor |
| Cost dashboard (metric) | ❌ | `gen_ai.client.token.usage` OTel metric not emitted by OneAgent |
| Service health tile | ✅ | OneAgent FastAPI sensor captures HTTP spans with status codes |
| Agent quick filter | N/A | Direct SDK, no agent framework |
| Provider quick filter | ✅ expected | Provider identity expected from experimental Mistral AI sensor |
| Guardrails | N/A | Not applicable |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.input.messages` / `gen_ai.output.messages` | Prompt capture not available (experimental sensor limitation) |
| `gen_ai.client.operation.duration` | OneAgent does not emit this OTel metric; all latency charts empty |
| `gen_ai.client.token.usage` (metric) | OneAgent does not emit this OTel metric; cost dashboard metric tiles empty |

## What to fix in the example app

**1. Enable the experimental Mistral AI sensor**

Enable the experimental **Mistral AI** sensor in Settings → OneAgent features (search "Mistral"). Restart the Python process after enabling.

**2. Enable the Python FastAPI sensor**

Enable the **Python FastAPI** sensor so HTTP entry-point spans nest the AI provider call correctly.

**3. Add prompt content via manual OTel instrumentation**

Prompt content is not available via the experimental sensor. To populate the prompts view with input/output messages, add manual OTel instrumentation — wrap `chat.complete()` with a custom span and set `gen_ai.input.messages` / `gen_ai.output.messages` attributes — or wait for a supported sensor. Token counts can be extracted from `response.usage.prompt_tokens` → `gen_ai.usage.input_tokens` and `response.usage.completion_tokens` → `gen_ai.usage.output_tokens`.

**4. Add an OTel metrics pipeline for latency and cost charts**

OTel metrics (`gen_ai.client.operation.duration`, `gen_ai.client.token.usage`) are not emitted by OneAgent. If latency charts and the cost dashboard metric tiles are required, add a separate OTel metrics pipeline.
