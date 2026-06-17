# Groq — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `groq/oneagent/app.py` | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `groq` SDK (`groq.Groq`) — bare SDK, no OTel auto-instrumentation in application code.
- **Provider**: Groq (`llama-3.1-8b-instant` model, default `llama-3.1-8b-instant`); uses an OpenAI-compatible REST API internally but does NOT use the `openai` package.
- **OTel setup**: No application-level OTel or Traceloop configuration. The app is a minimal FastAPI service deployed to Kubernetes. Instrumentation is expected to come from the Dynatrace OneAgent injected at the pod level — the OneAgent provides auto-instrumentation for supported runtimes and may capture generic HTTP-level spans and process-level metadata. OneAgent does NOT have specific gen_ai instrumentation for the Groq SDK; it may capture HTTP spans but will not emit `gen_ai.*` attributes. There is no `gen_ai.*` span attribute emission from the app code itself.

## Verdict: FAIL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ❌ | No `gen_ai.provider.name` or `gen_ai.system` emitted from app code; OneAgent has no specific Groq SDK instrumentation |
| `service.name` | ⚠️ | Likely set by OneAgent from K8s pod/deployment metadata; not explicitly set in app code |
| `gen_ai.request.model` | ❌ | Not emitted from app code; would require dedicated Groq SDK instrumentation |
| `gen_ai.response.model` | ❌ | Not emitted from app code |
| `gen_ai.usage.input_tokens` | ❌ | Not emitted from app code |
| `gen_ai.usage.output_tokens` | ❌ | Not emitted from app code |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ❌ | No `gen_ai.provider.name` or `gen_ai.system` — spans will not qualify as GenAI spans in DT AI Observability |
| Prompts — content | ❌ | No `gen_ai.input.messages` / `gen_ai.output.messages` / legacy fallbacks emitted |
| Prompts — model column | ❌ | No `gen_ai.request.model` emitted |
| Latency charts | ❌ | No `gen_ai.client.operation.duration` metric |
| Cost dashboard (span tokens) | ❌ | No token count attributes on spans |
| Cost dashboard (metric) | ❌ | No `gen_ai.client.token.usage` metric (AR-044); no metrics pipeline |
| Service health tile | ❌ | No OTel spans with `span.status_code` from GenAI calls |
| Agent quick filter | N/A | Groq SDK is used directly — no agent framework |
| Provider quick filter | ❌ | No provider identity attribute |
| Guardrails (Azure) | N/A | Not Azure |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | N/A | Not OpenAI package |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|--------------------|
| All GenAI spans | ❌ Empty | `gen_ai.provider.name` or `gen_ai.system` (AR-001/AR-002) — required gate |
| Prompts list / detail | ❌ Empty | All content attributes missing |
| Latency charts (p99/mean) | ❌ Empty | `gen_ai.client.operation.duration` (AR-025) not emitted |
| Cost dashboard tiles | ❌ Empty | `gen_ai.client.token.usage` metric (AR-044) not emitted; token span attributes absent |
| Service health tile | ❌ Empty | No OTel GenAI spans at all |
| Agent quick filter | N/A | Not an agent app |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | No evaluation bizevents emitted |

## Silent failures

Attributes absent that cause empty charts with no visible error:

| Attribute | Rule ID | Missing feature |
|-----------|---------|----------------|
| `gen_ai.provider.name` / `gen_ai.system` | AR-002/AR-001 | All GenAI views empty — spans do not qualify as AI spans |
| `gen_ai.client.operation.duration` | AR-025 | All latency charts empty |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost dashboard tiles show $0 silently; requires an OTel metrics pipeline |
| `gen_ai.token.type` (metric dimension) | AR-024 | Cost dashboard shows no split between input/output cost lanes |
| `span.status_code` | AR-047 | Service health tile shows all requests as successful if no OTel spans are present |

## What to fix in the example app

**1. Add OTel instrumentation (critical — no data flows to DT AI Observability without this)**

The app currently makes bare `Groq.chat.completions.create()` calls with no OTel instrumentation. OneAgent does not provide specific gen_ai instrumentation for the Groq SDK — only generic HTTP spans may be captured. To populate DT AI Observability views, add one of:

- **Option A — Traceloop SDK with `opentelemetry-instrumentation-groq`** (recommended for fastest path to full coverage):

```python
from traceloop.sdk import Traceloop
Traceloop.init(
    app_name="groq-demo",
    api_endpoint=os.environ["DT_ENDPOINT"],
    headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
    should_enrich_metrics=True,
    disable_batch=True,
)
# Traceloop auto-instruments Groq via opentelemetry-instrumentation-groq
```

- **Option B — OpenTelemetry Groq instrumentor** (community-maintained — verify package availability before use):

```python
from opentelemetry.instrumentation.groq import GroqInstrumentor
GroqInstrumentor().instrument()
```

- **Option C — Manual span creation**: Wrap each `client.chat.completions.create()` call in a custom OTel span and manually set `gen_ai.*` attributes.

**2. Add metrics pipeline for latency and cost charts**

If using Traceloop with `should_enrich_metrics=True`, metrics are synthesised automatically. If using manual instrumentation, add a `MeterProvider` with `OTLPMetricExporter` and record `gen_ai.client.operation.duration` and `gen_ai.client.token.usage`.

**3. Set `service.name` explicitly**

Add an OTel Resource with `service.name` to ensure consistent identification in DT:

```python
from opentelemetry.sdk.resources import Resource
resource = Resource.create({"service.name": "groq-demo"})
```

**4. Extract token counts from Groq response**

The Groq `chat.completions.create()` response includes `usage.prompt_tokens` and `usage.completion_tokens`. If instrumenting manually, map these to the modern attribute names on the span:

```python
span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
span.set_attribute("gen_ai.provider.name", "groq")
span.set_attribute("gen_ai.request.model", MODEL)
span.set_attribute("gen_ai.response.model", response.model)
```
