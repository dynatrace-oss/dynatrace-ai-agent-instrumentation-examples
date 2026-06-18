# Cohere — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `cohere/oneagent/app.py` | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `cohere` SDK (`cohere.ClientV2`) — bare SDK, no OTel auto-instrumentation in application code.
- **Provider**: Cohere
- **OTel setup**: No application-level OTel. Dynatrace OneAgent auto-instruments via the experimental **Cohere** sensor (Settings → OneAgent features → search "Cohere"). Also enable **Python FastAPI** sensor for HTTP entry-point spans. Experimental sensors are best-effort; not covered by DT support SLAs.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ expected | OneAgent experimental Cohere sensor emits provider identity |
| `service.name` | ✅ | Set by OneAgent from K8s/process metadata |
| `gen_ai.request.model` | ✅ expected | Captured by experimental Cohere sensor (best-effort) |
| `gen_ai.response.model` | ✅ expected | Captured by experimental Cohere sensor (best-effort) |
| `gen_ai.usage.input_tokens` | ✅ expected | Captured by experimental Cohere sensor (best-effort) |
| `gen_ai.usage.output_tokens` | ✅ expected | Captured by experimental Cohere sensor (best-effort) |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity expected from experimental Cohere sensor |
| Prompts — content | ❌ | Prompt capture (`gen_ai.input.messages` / `gen_ai.output.messages`) not available for experimental sensors; supported only for OpenAI and Bedrock |
| Prompts — model column | ✅ | `gen_ai.request.model` expected from experimental Cohere sensor |
| Latency charts | ❌ | OneAgent does not emit `gen_ai.client.operation.duration` OTel metric |
| Cost dashboard (span tokens) | ✅ expected | Token counts on spans expected from experimental Cohere sensor |
| Cost dashboard (metric) | ❌ | `gen_ai.client.token.usage` OTel metric not emitted by OneAgent |
| Service health tile | ✅ | OneAgent FastAPI sensor captures HTTP spans with status codes |
| Agent quick filter | N/A | Direct SDK, no agent framework |
| Provider quick filter | ✅ expected | Provider identity expected from experimental Cohere sensor |
| Guardrails | N/A | Not applicable |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Missing feature |
|-----------|----------------|
| `gen_ai.input.messages` / `gen_ai.output.messages` | Prompt capture not available (experimental sensor limitation) |
| `gen_ai.client.operation.duration` | OneAgent does not emit this OTel metric; all latency charts empty |
| `gen_ai.client.token.usage` (metric) | OneAgent does not emit this OTel metric; cost dashboard metric tiles empty |

## What to fix in the example app

**1. Enable the experimental Cohere sensor**

Enable the experimental **Cohere** sensor in Settings → OneAgent features (search "Cohere"). Restart the Python process after enabling.

**2. Enable the Python FastAPI sensor**

Enable the **Python FastAPI** sensor so HTTP entry-point spans nest the AI provider call correctly.

**3. Add prompt content via manual OTel instrumentation**

Prompt content is not available via the experimental sensor. To populate the prompts view with input/output messages, add manual OTel instrumentation — wrap `client.chat()` with a custom span and set `gen_ai.input.messages` / `gen_ai.output.messages` attributes — or wait for a supported sensor. Token counts can be extracted from `response.meta.billed_units.input_tokens` / `response.meta.billed_units.output_tokens`.

**4. Add an OTel metrics pipeline for latency and cost charts**

OTel metrics (`gen_ai.client.operation.duration`, `gen_ai.client.token.usage`) are not emitted by OneAgent. If latency charts and the cost dashboard metric tiles are required, add a separate OTel metrics pipeline.
