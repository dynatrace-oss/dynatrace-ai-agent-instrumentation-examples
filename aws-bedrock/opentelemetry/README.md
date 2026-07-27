## AWS Bedrock Tracing

This example shows how to instrument [AWS Bedrock](https://aws.amazon.com/bedrock/) LLM calls with OpenTelemetry and route traces and logs to Dynatrace.

Both the `Converse` and `Invoke` Bedrock APIs are covered, using the Boto3 client auto-instrumented via the [Traceloop SDK](https://www.traceloop.com/docs) and OpenTelemetry `BotocoreInstrumentor`. Traceloop enriches spans with `gen_ai.*` semantic conventions (model, token counts, finish reason) and the `@workflow`, `@task`, `@agent` decorators provide logical grouping in traces.

![AWS Bedrock Dynatrace Dashboard](./image1.png)

> [!TIP]
> For Dynatrace setup instructions, API token scopes, and advanced configuration, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

## Architecture

The app exports OTLP over HTTP directly to the Dynatrace OTLP endpoint. No collector is needed: the Traceloop SDK already emits `gen_ai.*` semantic conventions natively, so there is nothing to normalize on the way to Dynatrace.

```
Python app --> Dynatrace OTLP endpoint (/api/v2/otlp)
```

Metrics are exported with delta temporality (`OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`), which Dynatrace requires; cumulative OTLP metrics are rejected.

## Signals

| Signal | How | Details |
|---|---|---|
| **Traces** | `BotocoreInstrumentor` + Traceloop | One span per Bedrock API call — includes model ID, token usage, finish reason via `gen_ai.*` attributes |
| **Logs** | `OTLPLogExporter` (HTTP) | Python `logging` bridged to OTel; correlated to the active trace span |

All spans are grouped into logical `@workflow` / `@task` / `@agent` spans via Traceloop decorators.

## How to use

### Prerequisites

- Python 3.9+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- AWS credentials configured (`aws configure` or environment variables) with Bedrock access in `us-east-1`
- A Dynatrace environment with an API token that has the **`openTelemetryTrace.ingest`**, **`metrics.ingest`**, and **`logs.ingest`** scopes

### Install dependencies

```bash
make install
```

### Configure

Copy `.env.sample` to `.env` and set `DT_ENDPOINT`, `DT_API_TOKEN`, and your AWS credentials. The Makefile sources `.env` automatically.

```bash
# .env
DT_ENDPOINT=https://<YOUR_ENV_ID>.live.dynatrace.com
DT_API_TOKEN=dt0c01.****
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
```

### Run

```bash
make run
```

The script runs continuously, calling both the Converse and Invoke APIs every 5 seconds. Stop it with `Ctrl+C`.

### Verify in Dynatrace

```dql
fetch spans, from:now()-1h
| filter service.name == "bedrock_example_app"
| sort timestamp desc
| limit 50
```

## Files

| File | Description |
|---|---|
| `main.py` | Fully instrumented entrypoint — auto-instruments Boto3, sets up Traceloop, runs a continuous loop calling both APIs |
| `converse.py` | Minimal standalone example using the Converse API (no instrumentation) |
| `invoke.py` | Minimal standalone example using the Invoke API (no instrumentation) |
| `guard_rail_metrics.py` | Fetches Bedrock Guardrail metrics from CloudWatch (intervention count, latency, text units) |
