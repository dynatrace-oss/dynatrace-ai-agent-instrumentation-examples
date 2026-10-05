# CrewAI + Dynatrace

This sample instruments a [CrewAI](https://docs.crewai.com) agent with Dynatrace using [OpenLLMetry](https://github.com/traceloop/openllmetry) (Traceloop SDK). `make run` exports straight to Dynatrace with no collector; `make run-collector` adds a local OpenTelemetry Collector that derives the [GenAI agent duration metrics](#derived-agent-metrics) from the spans.

## What this sample does

- Runs a FastAPI server exposing `POST /haiku`
- Each request spins up a CrewAI `Poet` agent that writes a haiku using Azure OpenAI
- Exports traces and metrics directly to Dynatrace via OTLP HTTP, or through a local collector when started with `make run-collector`

## Derived agent metrics

`make run-collector` starts an OpenTelemetry Collector (`otel-collector-config.yaml`) that derives two GenAI semconv metrics from the CrewAI spans, with no application change:

| Metric | Derived from |
|---|---|
| `gen_ai.invoke_agent.duration` | the agent execution span (`<role>.agent`, `traceloop.span.kind = agent`) |
| `gen_ai.invoke_workflow.duration` | the crew kickoff span (`crewai.workflow`) |

Both are Histograms in seconds, exported with delta temporality because Dynatrace OTLP metric ingest rejects cumulative metrics.

> [!NOTE]
> The metric branches key on `traceloop.span.kind` and the span name, not on `gen_ai.operation.name`. `opentelemetry-instrumentation-crewai` sets `gen_ai.operation.name = invoke_agent` on three *nested* span types at once --- the crew kickoff, the agent execution, and the task execution --- so filtering on the enum would fold all three boundaries into one histogram and record roughly the same wall-clock three times. The collector does not rewrite the enum: the labelling is wrong upstream, and correcting it here would hide the problem and diverge from what the same SDK reports elsewhere.

The collector also renames `service.name` to `crewai-collector`, so a collector run stays distinguishable from a direct-export run in Dynatrace.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv`)
- A Dynatrace API token with `openTelemetryTrace.ingest` and `metrics.ingest`
- An Azure OpenAI endpoint and key

## Environment

Copy `.env.sample` to `.env` and fill in the values:

```env
DT_ENDPOINT=https://<tenant>.live.dynatrace.com
DT_API_TOKEN=dt0c01....

AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_API_KEY=...
OPENAI_API_VERSION=2024-07-01-preview
MODEL=azure/<deployment>
```

## Install and run

```bash
cd crewai/opentelemetry
make install
make run
```

Then in a second terminal:

```bash
make request
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Create venv and install dependencies via uv |
| `make run` | Start the FastAPI app on port 8000, exporting straight to Dynatrace |
| `make run-collector` | Start the OTel Collector, then the app exporting through it (adds the derived agent metrics) |
| `make request` | POST /haiku to localhost:8000 |
| `make stop` | Stop and remove the collector container |
| `make logs` | Tail the collector logs |

## Dynatrace views

After a few minutes, refresh the Dynatrace dashboard and you should see it being populated.

Explore the way your crews run, which models are used, how your token usage is attributed and which agents are spending the most time active.

Leverage the dashboard filters to filter (some) tiles to show data for only selected crews or flows.

Remember that you can drilldown into the end-to-end trace whenever a `trace.id` is shown. Just right click the trace ID and "open with" `Distributed Tracing`.

You can also open the Dynatrace `Distributed Tracing` view and filter for `service.name = crewai`.

In the Dynatrace **AI Observability** app you can filter by service, agent name, or model to explore token usage, cost breakdown, and latency across your crew runs.

![CrewAI Dynatrace Dashboard](assets/crewai_dashboard.png)

![distributed trace](assets/crewai_distributed_trace.png)

![Prompt and completion captured in Dynatrace AI Observability](assets/prompt.png)

![Agent activity and token usage per agent in Dynatrace AI Observability](assets/agent.png)

| View | What to look for |
|------|-----------------|
| **Distributed Tracing** | Filter by `service.name = crewai` |
| **AI Observability** | Token usage, latency, agent name per request |
| **Dashboard** | Upload `CrewAI Observability.json` for the prebuilt view |
