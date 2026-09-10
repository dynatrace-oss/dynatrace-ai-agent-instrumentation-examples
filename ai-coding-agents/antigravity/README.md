## Google Antigravity

This example shows how to enable [OpenTelemetry](https://opentelemetry.io/) tracing in the [Google Antigravity Python SDK](https://github.com/google-antigravity/antigravity-sdk-python) and route the data to Dynatrace for AI Observability of agent turns, tool calls and reasoning steps.

Unlike the CLI-based coding agents in this section, Antigravity is an SDK: telemetry is not switched on by an environment variable. The SDK ships OTel hooks in `google.antigravity.utils.otel`, but they are opt-in, and the application owns the `TracerProvider`. Both are wired up in [`app.py`](./app.py).

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

Two things are required, and neither happens automatically:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.utils import otel as otel_hooks

# 1. Configure a TracerProvider with an OTLP exporter pointed at Dynatrace.
#    The SDK reads no OTEL_* variables of its own.
trace.set_tracer_provider(provider)

# 2. Pass the OTel hooks to the agent config.
config = LocalAgentConfig(
    tools=[...],
    hooks=otel_hooks.get_otel_hooks(agent_name="observability-assistant"),
)
```

Install the OTel extra so the hooks are importable:

```bash
pip install 'google-antigravity[otel]'
```

### Spans

| Span name | `gen_ai.operation.name` | Notes |
|---|---|---|
| `antigravity.session` | _(none)_ | Root span, one per `Agent` context manager |
| `invoke_agent <name>` | `invoke_agent` | One per turn; carries `gen_ai.agent.name`. Subagents get their own nested span |
| `antigravity.step.<n>` | _(none)_ | One per reasoning step; carries `antigravity.step.index`, `.type`, `.status` |
| `execute_tool <name>` | `execute_tool` | One per tool call; carries `gen_ai.tool.name` |

The SDK does not put `gen_ai.request.model`, `gen_ai.response.model` or token counts on any span, and it emits no metrics. `gen_ai.provider.name` is set on the OTel Resource by [`app.py`](./app.py) rather than by the SDK.

### Derived metrics

Because the SDK emits no metrics, the optional Collector path in [`collector.yaml`](./collector.yaml) derives the two GenAI agent duration metrics the AI Observability app charts, using two `span_metrics` connectors:

| Metric | Derived from |
|---|---|
| `gen_ai.invoke_agent.duration` | `invoke_agent` spans, dimensioned by `gen_ai.agent.name` |
| `gen_ai.execute_tool.duration` | `execute_tool` spans, dimensioned by `gen_ai.tool.name` |

This example pins the collector to `ghcr.io/observiq/bindplane-agent:1.107.0`. The pin means a future version bump surfaces normalization changes in the e2e test.

## How to use

### Prerequisites

- Python 3.10+ (the SDK ships a compiled runtime binary, so install from PyPI rather than from a repository clone)
- A Gemini API key (`GEMINI_API_KEY` or `GOOGLE_API_KEY`)
- A Dynatrace environment with an API token carrying the `openTelemetryTrace.ingest` and `metrics.ingest` scopes
- Docker, only for the Collector path

### Configure Dynatrace credentials

```bash
cp .env.example .env   # then fill in DT_OTEL_ENDPOINT, DT_API_TOKEN, GEMINI_API_KEY
```

`DT_OTEL_ENDPOINT` is the base URL (`https://<environment-id>.live.dynatrace.com/api/v2/otlp`), with no `/v1/traces` suffix.

### Verify the transport

```bash
make install
source activate.sh
.venv/bin/python test_connection.py
```

This sends one representative trace without calling Gemini, so a failure here is an endpoint, token or network problem rather than an SDK problem.

### Run the agent

```bash
make run              # export traces straight to Dynatrace
make run-collector    # export via a local Collector that also derives the duration metrics
make stop             # remove the Collector container
```

### Dashboard

Import [`antigravity-monitoring-dashboard.json`](./antigravity-monitoring-dashboard.json) into Dynatrace Dashboards. It charts agent invocations, tool executions, failures, the derived duration metrics, and a recent-span table.

## Files

| File | Purpose |
|---|---|
| [`app.py`](./app.py) | The instrumented agent: TracerProvider setup plus OTel hook registration |
| [`activate.sh`](./activate.sh) | Sourceable env var setup from `.env` |
| [`collector.yaml`](./collector.yaml) | Optional Collector: forwards to Dynatrace and derives the agent/tool duration metrics |
| [`test_connection.py`](./test_connection.py) | Transport check that needs no Gemini API key |
| [`antigravity-monitoring-dashboard.json`](./antigravity-monitoring-dashboard.json) | Importable dashboard |
| [`Makefile`](./Makefile) | `install`, `run`, `run-collector`, `stop`, `logs` |
