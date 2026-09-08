## AWS Bedrock Tracing

This example shows how to instrument [AWS Bedrock](https://aws.amazon.com/bedrock/) LLM calls with OpenTelemetry and route traces, metrics, and logs to Dynatrace.

Both the `Converse` and `Invoke` Bedrock APIs are covered, using the Boto3 client auto-instrumented via the [Traceloop SDK](https://www.traceloop.com/docs). Traceloop enriches spans with `gen_ai.*` semantic conventions (model, token counts, finish reason) and the `@workflow`, `@task`, `@agent` decorators provide logical grouping in traces.

![AWS Bedrock Dynatrace Dashboard](./image1.png)

> [!TIP]
> For Dynatrace setup instructions, API token scopes, and advanced configuration, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

## Architecture

The example routes via a local [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/), which forwards to Dynatrace. This is required because the Traceloop SDK exports over gRPC, while Dynatrace ingests OTLP over HTTP/protobuf.

```
Python app → OTel Collector (localhost:4318) → Dynatrace OTLP endpoint
```

## Signals

| Signal | How | Details |
|---|---|---|
| **Traces** | Traceloop `BedrockInstrumentor` | One span per Bedrock API call; includes model ID, token usage, finish reason via `gen_ai.*` attributes |
| **Metrics** | Traceloop (`should_enrich_metrics=True`) | OTel GenAI client metrics `gen_ai.client.token.usage` and `gen_ai.client.operation.duration`, used by the AI Observability app's cost and latency charts |
| **Logs** | `OTLPLogExporter` (HTTP) | Python `logging` bridged to OTel; correlated to the active trace span |

All spans are grouped into logical `@workflow` / `@task` / `@agent` spans via Traceloop decorators.

### Derived agent metrics

The Traceloop decorators tag their spans with `traceloop.span.kind` but never set `gen_ai.operation.name`, so the GenAI agent metrics have nothing to key on out of the box. The collector config closes that gap without touching application code:

1. `transform/traceloop_operation_name` maps `traceloop.span.kind` onto the spec enum --- `agent` to `invoke_agent`, `workflow` to `invoke_workflow` --- and only where the enum is absent, so the `chat` value that `BedrockInstrumentor` sets on the LLM spans is never overwritten. `task` is left unmapped; it is an arbitrary function boundary, not a spec operation.
2. Two `span_metrics` connectors then derive `gen_ai.invoke_agent.duration` and `gen_ai.invoke_workflow.duration` (Histogram, seconds) from those spans.

`gen_ai.execute_tool.duration` is not derived here: the demo uses no `@tool` decorator, so there is no tool span to measure.

> [!IMPORTANT]
> Dynatrace OTLP metric ingest accepts **delta** temporality only and rejects cumulative metrics with HTTP 400. The app sets `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` before initializing Traceloop so the GenAI client metrics are accepted.

## Guardrails

`run_converse_guardrail_trigger()` sends prompts that violate a configured [Bedrock Guardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) so you can see blocked requests in Dynatrace. When `BEDROCK_GUARDRAIL_ID` is set, every Converse call attaches the guardrail with `trace: enabled`, and the instrumentation (`opentelemetry.instrumentation.bedrock`) maps the assessment onto the span:

- `gen_ai.response.finish_reasons = ["content_filter"]` and an `Input blocked` output message
- `gen_ai.bedrock.guardrail.activation`, `.input_filter`, `.topics`, `.content`, `.sensitive_info`
- `gen_ai.guardrail.id` / `.version`

Set `BEDROCK_GUARDRAIL_ID` (and optionally `BEDROCK_GUARDRAIL_VERSION`, default `DRAFT`) to enable it; without it the guardrail story is skipped.

> [!NOTE]
> This is the **in-trace** guardrail signal. `guard_rail_metrics.py` is a separate helper that pulls Bedrock Guardrail **metrics** (intervention count, latency, text units) from CloudWatch — a different data path, not part of the traced run.

## Multi-agent turn: input/output correlation in the Prompts view

Agents that fan a single user turn out into several Bedrock calls (a router, one or more specialist agents, an LLM-as-judge) expose a correlation gap in the Prompts view. Traceloop stamps `gen_ai.*` on each **model-call** span, but not on the enclosing `@workflow` / `@agent` span. Because the Prompts view pairs input to output per `gen_ai` span, the intermediate calls produce half-rows (an input with no text output when the model returns a tool call, or an output with no user input when the input is a tool result), and no single span holds "user question to final answer".

`run_multiagent_turn()` in `main.py` reproduces this and demonstrates the fix:

| Fix | Where | What it does |
|---|---|---|
| **Turn-level correlation** | `_stamp_turn_io()` | Records the whole turn on the **agent span** (`@agent`) so one clean `input -> output` record exists, using the message form (`gen_ai.input.messages` / `gen_ai.output.messages`) from the Dynatrace semantic dictionary. The span is typed as an agent (`gen_ai.operation.kind=agent`, `gen_ai.agent.name`) rather than a model call. Only the message form is set: the Prompts renderer appends both the flat form (`gen_ai.prompt.N` / `gen_ai.completion.0`) and the message form, so setting both would render the same turn twice. `gen_ai.provider.name=aws.bedrock` is set because the agent is Bedrock-backed; it is also what makes the app treat the span as a GenAI span (its filter is `isNotNull(gen_ai.system) or isNotNull(gen_ai.provider.name)`), so the turn shows in the Prompts view. |

The router (`route_intent`) and specialist (`answer_agent`) calls still emit their own `gen_ai` model-call spans, so the Prompts view shows them as separate rows alongside the turn: the turn appears as an **Agent** row (it carries `gen_ai.agent.name`) and the internal steps as **LLM** rows. This is expected — the fix is that a correct turn-level `input -> output` record now exists, not that the steps disappear. If you want a conversation view with only turns, suppress the internal rows at the pipeline layer (for example an OpenPipeline DQL processor or OTel Collector `transform` that drops the internal spans, or removes their `gen_ai.*` attributes so they fall out of the app's GenAI filter, matched by `traceloop.entity.name` / `span.name`).

> [!NOTE]
> This is a demonstration, so the multi-agent turn is simplified from a real deployment: the fan-out is sequential rather than parallel with a synthesis step.

## How to use

### Prerequisites

- Python 3.9+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- AWS credentials configured (`aws configure` or environment variables) with Bedrock access in `us-east-1`
- A running [OpenTelemetry Collector](#opentelemetry-collector) forwarding to Dynatrace
- A Dynatrace environment with an API token that has the **`openTelemetryTrace.ingest`**, **`metrics.ingest`**, and **`logs.ingest`** scopes
- Optional, for the guardrail story: set `BEDROCK_GUARDRAIL_ID` (and optionally `BEDROCK_GUARDRAIL_VERSION`, default `DRAFT`). When unset, the guardrail story is skipped

### Install dependencies

```bash
make install
```

### Configure the OTel Collector

Add the following to your collector config to receive from the app and forward to Dynatrace:

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

exporters:
  otlphttp:
    endpoint: https://<YOUR_ENV_ID>.live.dynatrace.com/api/v2/otlp
    headers:
      Authorization: "Api-Token <YOUR_DT_TOKEN>"

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlphttp]
    logs:
      receivers: [otlp]
      exporters: [otlphttp]
```

After you saved your `config.yaml`, you can start the collector with
```bash
docker run \
  -p 127.0.0.1:4317:4317 \
  -p 127.0.0.1:4318:4318 \
  -p 127.0.0.1:55679:55679 \
  --mount type=bind,source="$(pwd)"/config.yaml,target=/config.yaml,readonly \
  -it \
  otel/opentelemetry-collector:0.151.0  \
  --config=/config.yaml
```

### Run

```bash
make run                    # all four stories
make run STORY=multiagent   # or a single story: converse | guardrails | invoke | multiagent
```

The script runs continuously, replaying the selected story (or all four) every 5 seconds. Stop it with `Ctrl+C`.

To confirm the turn-level correlation, open the Prompts view and filter to your service (`bedrock_example_app` by default, or your `OTEL_SERVICE_NAME` if you set one): the `multiagent_turn` agent span appears as one **Agent** row with the question as input and the answer as output, and the internal `route_intent` / `answer_agent` model calls appear as separate **LLM** rows (suppress these at the pipeline layer if you want a turns-only conversation view).

### Verify in Dynatrace

```dql
fetch spans, from:now()-1h
| filter service.name == "bedrock_example_app"  // or your OTEL_SERVICE_NAME
| sort timestamp desc
| limit 50
```

## What this example demonstrates

`main.py` runs four independent stories in a single loop; each produces its own spans so you can look at them in isolation in the Prompts view.

| Story | Driver in `main.py` | What to look for in Dynatrace |
|---|---|---|
| **1. Converse API** | `run_converse()` | One `gen_ai` span per Converse call: model ID, token usage, finish reason |
| **2. Invoke API** | `run_invoke()` / `run_invoke_extra()` | Same signals via the alternate Bedrock Invoke API |
| **3. Guardrails** | `run_converse_guardrail_trigger()` | A blocked request: `gen_ai.response.finish_reasons=["content_filter"]` plus `gen_ai.bedrock.guardrail.*` (see [Guardrails](#guardrails)) |
| **4. Multi-agent turn** | `run_multiagent_turn()` | Turn-level input/output correlation on the agent span (see [Multi-agent turn](#multi-agent-turn-inputoutput-correlation-in-the-prompts-view)) |

By default all four run in one loop. To look at a single story with a focused trace, select it with the `STORY` variable (or a comma-separated list):

```bash
make run                    # all four (default)
make run STORY=guardrails   # just the guardrail story
make run STORY=converse,invoke
```

## Files

| File | Description |
|---|---|
| `main.py` | Fully instrumented entrypoint; auto-instruments Boto3, sets up Traceloop, and runs the four stories (converse, guardrails, invoke, multiagent) in a continuous loop, selectable via `STORY` |
| `converse.py` | Minimal standalone example using the Converse API (no instrumentation) |
| `invoke.py` | Minimal standalone example using the Invoke API (no instrumentation) |
| `guard_rail_metrics.py` | Fetches Bedrock Guardrail metrics from CloudWatch (intervention count, latency, text units) |
