# AWS Bedrock + OpenInference Demo

Demonstrates tracing LangChain + AWS Bedrock API calls with Dynatrace via OpenInference instrumentation. The app exports spans over OTLP to a local Bindplane collector, which normalizes them and forwards them to Dynatrace.

## How it works

OpenInference uses its own semantic conventions (`llm.model_name`, `llm.token_count.*`, etc.) that the Dynatrace AI Observability app does not natively understand. This example normalizes them to the Dynatrace `gen_ai.*` format in the collector, so no Dynatrace-side configuration is needed:

```
App  ->  Bindplane collector (genainormalizer + transform)  ->  Dynatrace Grail
```

The app knows only about `http://localhost:4318`; the collector is the component that authenticates with Dynatrace (`DT_ENDPOINT`, `DT_API_TOKEN`) and forwards spans. The pipeline runs two processors (see [`otelcol-config.yaml`](otelcol-config.yaml)):

1. **`gen_ai_normalizer`** (source `openinference`, `remove_originals: true`) maps OpenInference attributes to `gen_ai.*` and reconstructs the flattened `llm.input_messages.N.*` / `llm.output_messages.N.*` attributes into `gen_ai.input.messages` and `gen_ai.output.messages` JSON. `remove_originals` drops the raw `llm.*` attributes so exported spans carry only `gen_ai.*` fields.
2. **`transform/response_model`** mirrors `gen_ai.request.model` to `gen_ai.response.model`, which the AI Observability app requires and OpenInference has no separate field for.

The collector is pinned to `ghcr.io/observiq/bindplane-agent:1.104.0` (Bindplane Distro for OpenTelemetry), which tracks OTel Collector contrib v0.156.0 and bundles the `genainormalizer` processor. The pin means a future version bump surfaces normalization changes in the e2e test.

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
| `BEDROCK_MODEL_ID` | No | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Bedrock model ID |
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
