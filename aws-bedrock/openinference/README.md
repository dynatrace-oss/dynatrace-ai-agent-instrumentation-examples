# AWS Bedrock + OpenInference Demo

Demonstrates tracing AWS Bedrock API calls (via the boto3 `converse` API) with Dynatrace via OpenInference instrumentation (`BedrockInstrumentor`). The app emits native OpenTelemetry GenAI semantic-convention attributes and exports spans over OTLP to a local Bindplane collector, which forwards them to Dynatrace.

## How it works

The app enables OpenInference's native OTel GenAI semantic conventions, so spans include `gen_ai.*` attributes alongside OpenInference attributes (`llm.model_name`, `llm.token_count.*`, etc.). The collector does not need to normalize or rebuild those attributes; it only fills `gen_ai.response.model` from the request model when Bedrock's Converse response does not provide it:

```
App  ->  Bindplane collector (response-model fallback)  ->  Dynatrace Grail
```

The app knows only about `http://localhost:4318`; the collector is the component that authenticates with Dynatrace (`DT_ENDPOINT`, `DT_API_TOKEN`) and forwards spans. The collector runs a small response-model fallback and derives metrics from the native span attributes (see [`otelcol-config.yaml`](otelcol-config.yaml)):

1. **`transform/response_model`** mirrors `gen_ai.request.model` to `gen_ai.response.model` when the Bedrock response does not include a separate model value.
2. **Metrics connectors** derive `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` from the native `gen_ai.*` span attributes.

The collector is pinned to the Bindplane Distro for OpenTelemetry image in the Makefile. It derives metrics from the GenAI span attributes but does not rewrite the native attributes.

## Prerequisites

- Python 3.11+
- AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`)
- Bedrock model access enabled in your AWS account
- Dynatrace tenant with an API token scoped to `openTelemetryTrace.ingest`

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
   - To use a different model, select it with `BEDROCK_MODEL_ID`, for example `BEDROCK_MODEL_ID=us.deepseek.r1-v1:0` for DeepSeek-R1
2. `make install` — install dependencies
3. `make run` — start the app on port 8000
4. `make request` — send a test haiku request (in a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DT_ENDPOINT` | Yes | — | Dynatrace tenant URL (e.g. `https://abc12345.live.dynatrace.com`) |
| `DT_API_TOKEN` | Yes | — | Required scopes for OpenTelemetrcs ingest. See [Dynatrace documentation](https://docs.dynatrace.com/docs/shortlink/api-otlp-traces). |
| `AWS_ACCESS_KEY_ID` | Yes | — | AWS access key ID |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | AWS secret access key |
| `AWS_DEFAULT_REGION` | No | `us-east-1` | AWS region |
| `BEDROCK_MODEL_ID` | No | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model ID |
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
