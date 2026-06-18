# Haystack (OneAgent) — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `haystack/oneagent/app.py` | **Profile**: azure | **Dashboard**: `azureai.dashboard.json`

## Instrumentation

- **Library**: `haystack-ai` (`Pipeline`, `AzureOpenAIGenerator`) — Haystack framework with Azure OpenAI backend; no application-level OTel setup.
- **Provider**: Azure OpenAI (`AzureOpenAIGenerator`)
- **OTel setup**: None. No Traceloop, no manual OTel SDK configuration.
- **`haystack.tracing.disable_tracing()`**: This call is **correct and intentional**. OneAgent instruments `Pipeline.run` directly at the bytecode level via its experimental Haystack sensor. Haystack's own built-in OTel tracer would conflict with that instrumentation if left enabled. The code comment confirms the reasoning: "OneAgent instruments Pipeline.run directly and the two tracers conflict". Do **not** remove this call.
- **OneAgent sensors**: The experimental **Haystack** sensor must be explicitly enabled in Settings → OneAgent features (search "Haystack"). The **Python FastAPI** sensor must also be enabled for HTTP entry-point spans. Experimental sensors are best-effort and are not covered by Dynatrace support SLAs; attribute collection may be incomplete.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ expected | OneAgent experimental Haystack sensor captures the underlying Azure OpenAI provider identity |
| `service.name` | ✅ | Set by OneAgent from K8s/process metadata |
| `gen_ai.request.model` | ✅ expected | Captured by experimental Haystack sensor (best-effort) |
| `gen_ai.response.model` | ✅ expected | Captured by experimental Haystack sensor (best-effort) |
| `gen_ai.usage.input_tokens` | ✅ expected | Captured by experimental Haystack sensor (best-effort) |
| `gen_ai.usage.output_tokens` | ✅ expected | Captured by experimental Haystack sensor (best-effort) |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity captured by experimental Haystack sensor |
| Prompts — content | ❌ | Prompt capture (`gen_ai.input.messages` / `gen_ai.output.messages`) is not available for experimental sensors; only supported for OpenAI and AWS Bedrock sensors |
| Prompts — model column | ✅ | `gen_ai.request.model` captured (best-effort) |
| Latency charts | ❌ | `gen_ai.client.operation.duration` OTel metric not emitted by OneAgent; OneAgent uses its own internal pipeline |
| Cost dashboard (span tokens) | ✅ expected | Token count attributes captured on spans by experimental sensor (best-effort) |
| Cost dashboard (metric) | ❌ | `gen_ai.client.token.usage` OTel metric not emitted by OneAgent |
| Service health tile | ✅ | FastAPI sensor captures HTTP spans with status codes |
| Agent quick filter | N/A | App uses a simple Haystack Pipeline — not an agent framework |
| Provider quick filter | ✅ expected | Provider identity captured by experimental Haystack sensor |
| Guardrails (Azure Content Safety) | ❌ | Azure Content Safety not configured in demo — AR-015/AR-016 not emitted |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate | N/A | Not applicable for this configuration |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.input.messages` / `gen_ai.output.messages` | — | Prompt content not available; experimental sensor limitation |
| `gen_ai.client.operation.duration` | AR-025 | Latency charts empty; OTel metric not emitted by OneAgent |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost dashboard metric tiles empty; OTel metric not emitted by OneAgent |
| Azure Content Safety attributes | AR-015/AR-016 | Guardrails panel empty; service not configured |

## What to fix in the example app

**1. `haystack.tracing.disable_tracing()` — keep this call**

This is correct. It prevents Haystack's internal OTel tracer from conflicting with OneAgent's bytecode-level Haystack sensor. Removing it would cause both tracers to run simultaneously and produce duplicate or corrupted telemetry.

**2. Enable the experimental Haystack sensor in OneAgent**

Navigate to Settings → OneAgent features, search for "Haystack", and enable the sensor. Restart the Python process after enabling. This is the source of all `gen_ai.*` span attributes for this app.

**3. Enable the Python FastAPI sensor**

Navigate to Settings → OneAgent features and enable the **Python FastAPI** sensor. This is required for HTTP entry-point spans and the service health tile.

**4. Prompt content not available via experimental sensor**

`gen_ai.input.messages` and `gen_ai.output.messages` capture is not supported for experimental sensors. It is available only for the supported OpenAI and AWS Bedrock sensors. For prompt content capture, the options are: wait for a supported Haystack sensor, or add manual OTel span annotation in application code.

**5. Azure Content Safety guardrails (AR-015/AR-016)**

Not configured in this demo. Requires Azure Content Safety service setup and instrumentation to emit `gen_ai.azure.content_safety.*` attributes.

**6. OTel metrics (latency and cost metric tiles)**

OneAgent does not emit `gen_ai.client.operation.duration` or `gen_ai.client.token.usage` OTel metrics. If these metric-based dashboard tiles are required, a separate OTel SDK metrics pipeline must be added to the application alongside OneAgent.
