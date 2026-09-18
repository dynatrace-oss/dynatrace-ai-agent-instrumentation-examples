# AWS Bedrock + OpenInference Demo

Demonstrates tracing AWS Bedrock API calls (via the boto3 `converse` API) with Dynatrace via OpenInference instrumentation (`BedrockInstrumentor`). The app enables OpenInference's native GenAI semantic conventions (`OPENINFERENCE_ENABLE_GENAI_SEMCONV=true`), then exports spans over OTLP to a local Bindplane collector that forwards traces and derives GenAI metrics.

## How it works

With native GenAI semantic convention emission enabled, `BedrockInstrumentor` emits `gen_ai.*` attributes directly on spans (alongside existing OpenInference attributes). Only two gaps that native emission doesn't cover are patched in the collector; there's no OpenInference-to-`gen_ai.*` normalization chain to maintain:

```
App  ->  Bindplane collector (attribute patches + metrics derivation + OTLP forward)  ->  Dynatrace Grail
```

The app knows only about `http://localhost:4318`; the collector is the component that authenticates with Dynatrace (`DT_ENDPOINT`, `DT_API_TOKEN`), forwards spans, and derives GenAI metrics from span attributes. The pipeline uses these components (see [`otelcol-config.yaml`](otelcol-config.yaml)):

1. **`transform/response_model`** mirrors `gen_ai.request.model` onto `gen_ai.response.model`, which native OpenInference emission never sets (Bedrock's Converse response carries no model id) but the AI Observability app requires.
2. **`transform/guardrail_operation_name`** sets `gen_ai.operation.name` to `GUARDRAIL` on the standalone `apply_guardrail` span, derived from the `openinference.span.kind` attribute OpenInference still emits — native emission has no GUARDRAIL-kind handling at all.
3. **`span_metrics` connector** derives `gen_ai.client.operation.duration` histograms from LLM spans.
4. **`signal_to_metrics` connector** derives `gen_ai.client.token.usage` metric points from `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`. Note this connector silently drops the whole datapoint if any of its non-optional `attributes` keys (including `gen_ai.response.model`) is missing from the span — which is why step 1 above matters even though `gen_ai.response.model` isn't otherwise required.
5. **`filter/genai_only`** scopes metric derivation to LLM spans (`gen_ai.request.model` present).

The collector is pinned to `ghcr.io/observiq/bindplane-agent:1.108.0` (Bindplane Distro for OpenTelemetry). The pin means a future version bump surfaces behavior changes in the e2e test.

## Prerequisites

- Python 3.11+
- AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`)
- Bedrock model access enabled in your AWS account
- Dynatrace tenant with an API token scoped to `openTelemetryTrace.ingest`

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install` — install dependencies
3. `make run` — start the app on port 8000
4. `make request` — send a test haiku request (in a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DT_ENDPOINT` | Yes | — | Dynatrace tenant URL (e.g. `https://abc12345.live.dynatrace.com`) |
| `DT_API_TOKEN` | Yes | — | Dynatrace API token with `openTelemetryTrace.ingest` scope |
| `AWS_ACCESS_KEY_ID` | Yes | — | AWS access key ID |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | AWS secret access key |
| `AWS_DEFAULT_REGION` | No | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | No | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model ID |
| `OPENINFERENCE_ENABLE_GENAI_SEMCONV` | No | `true` | Keep enabled to emit `gen_ai.*` attributes natively from OpenInference instrumentation |
| `OTEL_SERVICE_NAME` | No | `haiku-writer` | Service name reported in traces |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make help` | Show all available targets |
