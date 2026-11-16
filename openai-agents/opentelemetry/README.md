## OpenAI Agent SDK


This example contains a demo of a Customer Service Agent interface built on top of the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/). The original example code can be found in the [openai-cs-agents-demo](https://github.com/openai/openai-cs-agents-demo) GitHub repo.

![Trace View](../../assets/trace-view.png)

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).


This demo uses the OpenTelemetry project's own instrumentation for the Agents SDK, [`opentelemetry-instrumentation-openai-agents-v2`](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-openai-agents-v2), on top of the plain OpenTelemetry SDK. No vendor SDK is involved.

Setup lives in [`api.py`](./api.py):

```python
os.environ['OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE'] = "delta"

_resource = Resource.create({"service.name": "openai-cs-agents"})

_tracer_provider = TracerProvider(resource=_resource)
_tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{OTLP_ENDPOINT}/v1/traces", headers=headers))
)
trace.set_tracer_provider(_tracer_provider)

metrics.set_meter_provider(
    MeterProvider(
        resource=_resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{OTLP_ENDPOINT}/v1/metrics", headers=headers)
            )
        ],
    )
)

OpenAIAgentsInstrumentor().instrument(
    tracer_provider=_tracer_provider,
    system="azure.ai.openai",
    capture_message_content="span_only",
)
```

`system` sets `gen_ai.provider.name` (the default is `openai`), and `capture_message_content="span_only"` puts prompts and completions on span attributes, where Dynatrace reads them. The instrumentation also records `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` through the meter provider, exported with delta temporality because Dynatrace OTLP metric ingest rejects cumulative metrics.

The agents use the Responses API (`OpenAIResponsesModel` in [`main.py`](./main.py)). The Agents SDK only passes the response ID, response model and finish reasons to the instrumentation on that path; with chat completions those span attributes are missing.

The token is read from the `DT_API_TOKEN` environment variable first, falling back to `/etc/secrets/dynatrace_otel` for Kubernetes deployments.

### Derived agent metrics

`make run-collector` starts the app behind a local OpenTelemetry Collector (`otel-collector-config.yaml`) that derives three GenAI semconv metrics from the spans, with no change to the agent code:

| Metric | Derived from |
|---|---|
| `gen_ai.invoke_agent.duration` | the agent span (`gen_ai.operation.name = invoke_agent`) |
| `gen_ai.execute_tool.duration` | the function-tool span (`gen_ai.operation.name = execute_tool`) |
| `gen_ai.invoke_workflow.duration` | the per-trace root span (`Agent Workflow`) |

The instrumentation already sets the spec operation name on the agent and tool spans. The root workflow span is the gap: it is tagged `invoke_agent` like the agent spans below it, so `transform/operation_name` re-tags the `SERVER`-kind root as `invoke_workflow`. The same transform removes two artifacts of the instrumentation: the `unknown` operation name on the SDK's task and turn spans, which have no GenAI semconv equivalent, and the placeholder agent (`gen_ai.agent.name = "OpenAI Agent"`, `gen_ai.agent.id = "agent"`) it stamps on every span that is not a real agent span. Without the collector (`make run`), both artifacts reach Dynatrace as-is.

All three are Histograms in seconds, exported with delta temporality because Dynatrace OTLP metric ingest rejects cumulative metrics. The collector also renames `service.name` to `openai-cs-agents-collector`, so a collector run stays distinguishable from a direct-export run in Dynatrace.

When `OTEL_ENDPOINT` is set (which `make run-collector` does), traces, metrics and logs all go to the collector and the Dynatrace credentials live only in the collector config.

## How to use

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Azure OpenAI resource with a `gpt-4o` deployment
- A Dynatrace environment with an API token scoped to `openTelemetryTrace.ingest` and `metrics.ingest`

### Configure environment variables

```bash
# Dynatrace
export DT_ENDPOINT=https://<YOUR_ENV_ID>.live.dynatrace.com
export DT_API_TOKEN=dt0c01.<YOUR_TOKEN>

# Azure OpenAI
export AZURE_OPENAI_API_KEY=<YOUR_KEY>
export AZURE_OPENAI_ENDPOINT=https://<YOUR_RESOURCE>.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT=gpt-4o
# Optional; the Responses API needs 2025-03-01-preview or later
export AZURE_OPENAI_RESPONSES_API_VERSION=2025-04-01-preview
```

### Install and run

```bash
make install         # install Python dependencies
make run             # start the backend on port 8000, exporting straight to Dynatrace
make run-collector   # or: start it behind a collector that derives the agent metrics
make request         # send a test question (in a second terminal)
```

The backend API is available at [http://localhost:8000](http://localhost:8000). A Next.js frontend is available in the `ui/` folder:

```bash
cd ui && npm install && npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000).

![Trace View](../../assets/trace-view.png)