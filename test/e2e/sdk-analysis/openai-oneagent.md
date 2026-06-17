# OpenAI OneAgent — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `openai/oneagent/app.py` | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `openai` SDK (`openai >= 2.38.0`, `openai.OpenAI` client) — bare SDK, no OTel auto-instrumentation in application code.
- **Provider**: OpenAI (or Azure OpenAI depending on env vars — `OPENAI_API_BASE` / `OPENAI_API_VERSION` select Azure-compatible mode)
- **OTel setup**: No application-level OTel or Traceloop configuration. The app is a minimal FastAPI service. Instrumentation is expected to come from the Dynatrace OneAgent injected at the pod level. Unlike Cohere and Mistral, Dynatrace OneAgent does have auto-instrumentation support for the OpenAI Python SDK — however, two caveats apply: (1) the app uses **streaming** (`stream=True`), and OneAgent typically captures request/response attributes at span boundaries rather than mid-stream, meaning token counts and response model may not be captured reliably; (2) `openai >= 2.38.0` is a recent major version and OneAgent compatibility with this SDK version should be verified. There is no `gen_ai.*` span attribute emission from the app code itself.

## Verdict: FAIL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ⚠️ | OneAgent may emit `gen_ai.system` for OpenAI SDK calls, but streaming mode reduces reliability; version compatibility with `openai >= 2.38.0` unverified |
| `service.name` | ⚠️ | Likely set by OneAgent from K8s pod/deployment metadata; not explicitly set in app code |
| `gen_ai.request.model` | ⚠️ | May be captured by OneAgent at span start (pre-stream); not emitted from app code |
| `gen_ai.response.model` | ❌ | Response model is not available until stream completes; OneAgent cannot reliably capture mid-stream |
| `gen_ai.usage.input_tokens` | ❌ | Not emitted from app code; streaming chunks do not carry token counts until final chunk, which OneAgent may miss |
| `gen_ai.usage.output_tokens` | ❌ | Not emitted from app code; same streaming limitation as above |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ⚠️ | OneAgent may qualify spans as GenAI for OpenAI, but streaming reduces attribute completeness |
| Prompts — content | ❌ | No `gen_ai.input.messages` / `gen_ai.output.messages` / legacy fallbacks emitted from app code |
| Prompts — model column | ⚠️ | `gen_ai.request.model` may be captured at span start; response model unreliable with streaming |
| Latency charts | ❌ | No `gen_ai.client.operation.duration` metric; OneAgent does not synthesise OTel metrics |
| Cost dashboard (span tokens) | ❌ | Token count attributes not reliably captured due to streaming |
| Cost dashboard (metric) | ❌ | No `gen_ai.client.token.usage` metric (AR-044); no metrics pipeline |
| Service health tile | ⚠️ | OneAgent may emit process/HTTP spans; GenAI-specific `span.status_code` not guaranteed |
| Agent quick filter | N/A | OpenAI SDK is used directly — no agent framework |
| Provider quick filter | ⚠️ | Provider identity depends on OneAgent OpenAI support and streaming compatibility |
| Guardrails (Azure) | ⚠️ | Azure OpenAI mode possible via env vars; Azure Content Safety not wired up (AR-015/AR-016) |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | ❌ | No `gen_ai.openai.cache.*` attributes emitted |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ⚠️ Partial | `gen_ai.provider.name` / `gen_ai.system` may be present via OneAgent, but streaming limits completeness |
| Prompts list / detail | ❌ Empty | All content attributes missing |
| Latency charts (p99/mean) | ❌ Empty | `gen_ai.client.operation.duration` (AR-025) not emitted |
| Cost dashboard tiles | ❌ Empty | `gen_ai.client.token.usage` metric (AR-044) not emitted; token span attributes unreliable due to streaming |
| Service health tile | ⚠️ Partial | OneAgent HTTP/process spans present but not GenAI-qualified spans |
| Agent quick filter | N/A | Not an agent app |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.response.model` | AR-002 | Model column empty in prompts view; streaming prevents reliable capture |
| `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` | AR-003/AR-004 | Token counts absent — streaming final chunk not reliably captured by OneAgent |
| `gen_ai.client.operation.duration` | AR-025 | All latency charts empty — metric not synthesised by OneAgent |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost dashboard tiles show $0 silently; requires an OTel metrics pipeline |
| `gen_ai.token.type` (metric dimension) | AR-024 | Cost dashboard shows no split between input/output cost lanes |
| `span.status_code` | AR-047 | Service health tile shows all requests as successful if no OTel GenAI spans are present |

## What to fix in the example app

**1. Replace streaming with a non-streaming call (simplest fix for reliable OneAgent capture)**

The streaming call accumulates all chunks into a single string synchronously — there is no incremental consumer, so streaming provides no benefit here. Switching to a non-streaming call removes the mid-stream attribute capture problem entirely and allows OneAgent to capture request/response attributes reliably:

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "Write a haiku."}],
    max_completion_tokens=20,
    stream=False,
)
return response.choices[0].message.content or ""
```

**2. OR add explicit OTel via the community OpenAI instrumentor** (handles streaming via callbacks):

```python
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
OpenAIInstrumentor().instrument()
```

This instrumentor (from Traceloop/OpenLLMetry) wraps the OpenAI client and captures `gen_ai.*` attributes including token counts from the final streaming chunk.

**3. OR use the Traceloop SDK with `should_enrich_metrics=True`** (recommended for full coverage including metrics):

```python
from traceloop.sdk import Traceloop
Traceloop.init(
    app_name="openai-oneagent-demo",
    api_endpoint=os.environ["DT_ENDPOINT"],
    headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
    should_enrich_metrics=True,
    disable_batch=True,
)
# Traceloop auto-instruments the OpenAI SDK including streaming support
```

**4. Add metrics pipeline for latency and cost charts**

If using Traceloop with `should_enrich_metrics=True`, metrics are synthesised automatically. If using manual or community instrumentation, add a `MeterProvider` with `OTLPMetricExporter` and record `gen_ai.client.operation.duration` and `gen_ai.client.token.usage`.

**5. Set `service.name` explicitly**

Add an OTel Resource with `service.name` to ensure consistent identification in DT:

```python
from opentelemetry.sdk.resources import Resource
resource = Resource.create({"service.name": "openai-oneagent-demo"})
```

**6. Azure OpenAI: add Content Safety if required (AR-015/AR-016)**

If the app is deployed against Azure OpenAI (`OPENAI_API_BASE` set to an Azure endpoint), consider wiring up Azure Content Safety to populate guardrail views in the dashboard. Without this, AR-015 and AR-016 tiles remain empty with no visible error.
