## Google Antigravity

This example shows how to enable [OpenTelemetry](https://opentelemetry.io/) tracing in the [Google Antigravity Python SDK](https://github.com/google-antigravity/antigravity-sdk-python) and route the data to Dynatrace for AI Observability of agent turns, tool calls, reasoning steps, token usage and prompt content.

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

The SDK does not put the model, token counts or message content on any span, and it emits no metrics. All of that exists at runtime (`Conversation.last_turn_usage`, the prompt passed to the pre-turn hook, the response passed to the post-turn hook) but never reaches a span, so a collector rule cannot recover it. [`app.py`](./app.py) therefore subclasses the SDK's two turn hooks and adds, on the `invoke_agent` span:

| Attribute | Source |
|---|---|
| `gen_ai.request.model` | the configured model (`MODEL`, or the SDK default) |
| `gen_ai.usage.input_tokens` | `UsageMetadata.prompt_token_count` |
| `gen_ai.usage.output_tokens` | `candidates_token_count` + `thoughts_token_count` (thinking is billed as output) |
| `gen_ai.usage.cached_input_tokens` | `cached_content_token_count`, when non-zero (a subset of prompt tokens, so not added to the input total) |
| `gen_ai.input.messages` | the prompt handed to the pre-turn hook |
| `gen_ai.output.messages` | the response handed to the post-turn hook |
| `gen_ai.system_instructions` | the configured system instructions |

Subclassing rather than appending extra hooks is what enforces the ordering: the attributes must land after the turn span opens and before it closes, and the hook runner offers no way to say that.

Token counts are turn-level. A single agent turn makes several model invocations, and the SDK deliberately consolidated usage reporting at the turn and session level, so per-call granularity is not available.

`gen_ai.provider.name` is set on the OTel Resource, and `gen_ai.response.model` is mirrored from the request model by the collector, since the SDK reports no resolved model anywhere.

### Prompt capture

Message content is opt-in per the OTel GenAI semconv. It defaults to **on** here, because showing the prompt and response in Dynatrace is the point of the demo. To turn it off:

```bash
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false
```

Content is written to `gen_ai.input.messages` / `gen_ai.output.messages`, not the legacy indexed `gen_ai.prompt.N.content` attributes.

### Derived metrics

The SDK emits no metrics, so [`collector.yaml`](./collector.yaml) derives all four the AI Observability app charts:

| Metric | Derived from | Connector |
|---|---|---|
| `gen_ai.client.token.usage` | the token attributes above, one entry per direction | `signal_to_metrics` |
| `gen_ai.client.operation.duration` | `invoke_agent` span timing | `span_metrics` |
| `gen_ai.invoke_agent.duration` | `invoke_agent` span timing, by `gen_ai.agent.name` | `span_metrics` |
| `gen_ai.execute_tool.duration` | `execute_tool` span timing, by `gen_ai.tool.name` | `span_metrics` |

`signal_to_metrics` emits cumulative sums and offers no temporality setting, while Dynatrace accepts delta only and silently drops the rest, so a `cumulative_to_delta` processor scoped to `gen_ai.client.token.usage` converts it before export. The three `span_metrics` connectors are configured delta directly and are left alone.

One caveat worth knowing before you read the latency charts: `gen_ai.client.operation.duration` is derived from the agent turn, not from a single Gemini request, because the SDK opens no span around the client call. It therefore measures a whole turn (several model invocations plus tool execution). The turn is the narrowest boundary the SDK exposes, and the alternative is empty latency charts.

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

Import [`antigravity-monitoring-dashboard.json`](./antigravity-monitoring-dashboard.json) into Dynatrace Dashboards. It charts agent invocations, tool executions, failures, token usage by direction and model, the three derived duration metrics, and a prompt/response table.

## Files

| File | Purpose |
|---|---|
| [`app.py`](./app.py) | The instrumented agent: TracerProvider setup plus OTel hook registration |
| [`activate.sh`](./activate.sh) | Sourceable env var setup from `.env` |
| [`collector.yaml`](./collector.yaml) | Optional Collector: forwards to Dynatrace and derives the agent/tool duration metrics |
| [`test_connection.py`](./test_connection.py) | Transport check that needs no Gemini API key |
| [`antigravity-monitoring-dashboard.json`](./antigravity-monitoring-dashboard.json) | Importable dashboard |
| [`Makefile`](./Makefile) | `install`, `run`, `run-collector`, `stop`, `logs` |
