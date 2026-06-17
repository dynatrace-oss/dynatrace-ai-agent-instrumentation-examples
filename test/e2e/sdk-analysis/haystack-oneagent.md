# Haystack (OneAgent) — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.1 | **Path**: `haystack/oneagent/app.py` | **Profile**: azure | **Dashboard**: `azureai.dashboard.json`

## Instrumentation

- **Library**: `haystack-ai` (`Pipeline`, `AzureOpenAIGenerator`) — Haystack framework with Azure OpenAI backend; no application-level OTel setup.
- **Provider**: Azure OpenAI (`AzureOpenAIGenerator`, deployment `genai-demo`)
- **OTel setup**: `haystack.tracing.disable_tracing()` is called explicitly at startup, which actively suppresses Haystack's built-in OTel tracer. This means even Haystack-native OTel instrumentation is prevented from emitting spans. No Traceloop or manual OTel configuration is present. Instrumentation is expected from Dynatrace OneAgent at pod level, but OneAgent does not have specific Haystack framework instrumentation; it may capture HTTP-level calls to Azure OpenAI but will not emit `gen_ai.*` semantic convention attributes.

## Verdict: FAIL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ❌ | No `gen_ai.provider.name` or `gen_ai.system` emitted; `disable_tracing()` suppresses all Haystack OTel output |
| `service.name` | ⚠️ | Likely set by OneAgent from K8s pod/deployment metadata; not explicitly set in app code |
| `gen_ai.request.model` | ❌ | Not emitted; Haystack tracing disabled |
| `gen_ai.response.model` | ❌ | Not emitted; Haystack tracing disabled |
| `gen_ai.usage.input_tokens` | ❌ | Not emitted; Haystack tracing disabled |
| `gen_ai.usage.output_tokens` | ❌ | Not emitted; Haystack tracing disabled |

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
| Agent quick filter | N/A | App uses a simple Haystack Pipeline — not an agent framework |
| Provider quick filter | ❌ | No provider identity attribute |
| Guardrails (Azure Content Safety) | N/A | Azure OpenAI backend used but no Azure Content Safety configured — AR-015/AR-016 not applicable |
| Guardrails (Bedrock) | N/A | Not Bedrock |
| Cache hit rate (OpenAI) | N/A | Azure OpenAI endpoint used via Haystack generator, not direct OpenAI SDK |

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

**1. Remove `haystack.tracing.disable_tracing()` and configure Haystack's built-in OTel (critical — this call actively prevents any data from flowing to DT AI Observability)**

`haystack.tracing.disable_tracing()` was added to avoid a conflict between Haystack's internal tracer and OneAgent, but it also suppresses all `gen_ai.*` attribute emission. Remove it and instead configure Haystack's native OTel tracer to send directly to Dynatrace:

- **Option A — Haystack built-in OTel tracer** (recommended — preserves Haystack's `gen_ai.*` semantic conventions):

```python
from haystack.tracing import OpenTelemetryTracer
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
import opentelemetry.sdk.trace as trace_sdk
from opentelemetry.sdk.trace.export import BatchSpanProcessor

exporter = OTLPSpanExporter(
    endpoint=os.environ["DT_ENDPOINT"] + "/api/v2/otlp/v1/traces",
    headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
)
provider = trace_sdk.TracerProvider()
provider.add_span_processor(BatchSpanProcessor(exporter))
tracer = OpenTelemetryTracer(provider.get_tracer("haystack"))
# Do NOT call haystack.tracing.disable_tracing() — let Haystack use this tracer
```

Enable prompt content tracing via the environment variable:

```bash
HAYSTACK_CONTENT_TRACING_ENABLED=true
```

- **Option B — Traceloop SDK** (alternative if a unified instrumentation approach is preferred):

```python
from traceloop.sdk import Traceloop
Traceloop.init(
    app_name="haystack-demo",
    api_endpoint=os.environ["DT_ENDPOINT"],
    headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
    should_enrich_metrics=True,
    disable_batch=True,
)
```

**2. Add metrics pipeline for latency and cost charts**

If using Haystack's built-in OTel tracer (Option A), add a separate `MeterProvider` with `OTLPMetricExporter` to populate `gen_ai.client.operation.duration` and `gen_ai.client.token.usage`. If using Traceloop with `should_enrich_metrics=True`, metrics are synthesised automatically.

**3. Set `service.name` explicitly**

Add an OTel Resource with `service.name` to ensure consistent identification in DT:

```python
from opentelemetry.sdk.resources import Resource
resource = Resource.create({"service.name": "haystack-demo"})
provider = trace_sdk.TracerProvider(resource=resource)
```

**4. Azure Content Safety guardrails (AR-015/AR-016)**

Azure Content Safety guardrails are N/A for this app — no Azure Content Safety service is configured. If added in future, instrument the Content Safety client calls to emit `gen_ai.azure.content_safety.*` attributes.
