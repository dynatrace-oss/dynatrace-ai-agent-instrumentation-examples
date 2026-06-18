# Groq — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `groq/oneagent/app.py` | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `groq` SDK (`groq.Groq`) — bare SDK, no OTel auto-instrumentation in application code.
- **Provider**: Groq (`llama-3.1-8b-instant` model); uses an OpenAI-compatible REST API internally but does NOT use the `openai` package.
- **OTel setup**: No application-level OTel configuration. The app is a minimal FastAPI service. Instrumentation comes from the Dynatrace OneAgent injected at the pod level. OneAgent provides auto-instrumentation via the experimental **Groq** sensor (Settings → OneAgent features → search "Groq"). The **Python FastAPI** sensor must also be enabled for HTTP entry-point spans. Experimental sensors are best-effort and not covered by DT support SLAs; attribute collection and schema may change without notice.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | Expected via experimental Groq sensor — `gen_ai.system` or `gen_ai.provider.name` captured automatically |
| `service.name` | ✅ | Set by OneAgent from K8s pod/deployment metadata |
| `gen_ai.request.model` | ✅ | Expected via experimental Groq sensor |
| `gen_ai.response.model` | ✅ | Expected via experimental Groq sensor |
| `gen_ai.usage.input_tokens` | ✅ | Expected via experimental Groq sensor |
| `gen_ai.usage.output_tokens` | ✅ | Expected via experimental Groq sensor |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity captured by experimental Groq sensor |
| Prompts — content | ❌ | Prompt capture (`gen_ai.input.messages` / `gen_ai.output.messages`) is only available for OpenAI and AWS Bedrock; experimental sensors do not support it |
| Prompts — model column | ✅ | `gen_ai.request.model` expected via experimental sensor |
| Latency charts | ❌ | OneAgent does not emit OTel `gen_ai.client.operation.duration` metrics; separate OTel SDK pipeline required |
| Cost dashboard (span tokens) | ✅ | Token count attributes expected on spans via experimental sensor |
| Cost dashboard (metric) | ❌ | OneAgent does not emit `gen_ai.client.token.usage` metric; separate OTel SDK pipeline required |
| Service health tile | ✅ | Span status captured via experimental sensor |
| Agent quick filter | N/A | Groq SDK is used directly — no agent framework |
| Provider quick filter | ✅ | Provider identity attribute captured by experimental sensor |
| Guardrails (Azure) | N/A | Not Azure |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | N/A | Not OpenAI package |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ✅ Expected | Provider identity captured by experimental Groq sensor |
| Prompts list / detail | ⚠️ Partial | Model column populated; prompt/response content absent — experimental sensor limitation |
| Latency charts (p99/mean) | ❌ Empty | `gen_ai.client.operation.duration` (AR-025) not emitted by OneAgent |
| Cost dashboard tiles (span) | ✅ Expected | Token span attributes captured by experimental sensor |
| Cost dashboard tiles (metric) | ❌ Empty | `gen_ai.client.token.usage` metric (AR-044) not emitted by OneAgent |
| Service health tile | ✅ Expected | Span status captured |
| Agent quick filter | N/A | Not an agent app |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.input.messages` / `gen_ai.output.messages` | — | Prompt content not captured; experimental Groq sensor does not support prompt capture |
| `gen_ai.client.operation.duration` | AR-025 | All latency charts empty; OneAgent uses internal metrics pipeline, not OTel gen_ai metrics |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost dashboard metric tiles empty; OTel metrics pipeline not present |

## What to fix in the example app

**1. Enable the experimental Groq sensor in OneAgent features**

Go to Settings → OneAgent features → search "Groq" → enable the experimental sensor. Restart the monitored process. The sensor is best-effort; attribute collection and schema may change without notice and is not covered by DT support SLAs.

**2. Enable the Python FastAPI sensor**

Go to Settings → OneAgent features → enable **Python FastAPI** to capture HTTP entry-point spans.

**3. Prompt content — manual OTel span required**

Prompt capture is not available via the experimental Groq sensor. To capture message content, wrap `client.chat.completions.create()` in a manual OTel span:

```python
span.set_attribute("gen_ai.input.messages", ...)   # prompt messages as JSON
span.set_attribute("gen_ai.output.messages", ...)  # response messages as JSON
```

For token extraction, map from the Groq response:

```python
span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
```

**4. OTel metrics pipeline (optional — for latency and cost metric charts)**

OneAgent does not emit OTel `gen_ai.*` metrics. If latency charts and the cost metric dashboard tile are required, add a separate OTel SDK pipeline with a `MeterProvider` and `OTLPMetricExporter` to record `gen_ai.client.operation.duration` and `gen_ai.client.token.usage`.
