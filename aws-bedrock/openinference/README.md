# AWS Bedrock + OpenInference Demo

Demonstrates tracing AWS Bedrock API calls (via the boto3 `converse` API) with Dynatrace via OpenInference instrumentation (`BedrockInstrumentor`). The app exports spans over OTLP to a local Bindplane collector, which normalizes them and forwards them to Dynatrace.

## How it works

OpenInference uses its own semantic conventions (`llm.model_name`, `llm.token_count.*`, etc.) that the Dynatrace AI Observability app does not natively understand. This example normalizes them to the Dynatrace `gen_ai.*` format in the collector, so no Dynatrace-side configuration is needed:

```
App  ->  Bindplane collector (genainormalizer + transform)  ->  Dynatrace Grail
```

The app knows only about `http://localhost:4318`; the collector is the component that authenticates with Dynatrace (`DT_ENDPOINT`, `DT_API_TOKEN`) and forwards spans. The pipeline runs these processors (see [`otelcol-config.yaml`](otelcol-config.yaml)):

1. **`gen_ai_normalizer`** (source `openinference`, `remove_originals: false`) maps OpenInference attributes to `gen_ai.*` and reconstructs the flattened `llm.input_messages.N.*` / `llm.output_messages.N.*` attributes into `gen_ai.input.messages` and `gen_ai.output.messages` JSON.
2. **`transform/fix_input_messages`** / **`transform/fix_output_messages`** rebuild `gen_ai.input.messages` / `gen_ai.output.messages` by hand — `gen_ai_normalizer` otherwise emits both with an empty `parts` array for this demo; see [Known gaps & limitations](#known-gaps--limitations) below.
3. **`transform/response_model`** mirrors `gen_ai.request.model` to `gen_ai.response.model`, which the AI Observability app requires and OpenInference has no separate field for.
4. **`transform/cleanup_raw_attrs`** strips the raw `llm.*` attributes left behind by turning off `remove_originals`, so exported spans still end up `gen_ai.*`-only.

The collector is pinned to `ghcr.io/observiq/bindplane-agent:1.104.0` (Bindplane Distro for OpenTelemetry), which tracks OTel Collector contrib v0.156.0 and bundles the `genainormalizer` processor. The pin means a future version bump surfaces normalization changes in the e2e test.

## Known gaps & limitations

### genainormalizer drops message content (worked around locally)

`genainormalizer`'s `openinference` source reconstructs `gen_ai.input.messages` and `gen_ai.output.messages` with an empty `parts` array for every span this demo produces — [upstream issue](https://github.com/open-telemetry/opentelemetry-collector-contrib/issues/50133). The root cause: Bedrock's `converse` API takes `content` as an array even for a single plain-text block, so `openinference-instrumentation-bedrock` never sets the flat `message.content` string the normalizer's message-reconstruction path expects — it only nests text under the indexed `llm.{input,output}_messages.N.message.contents.M.message_content.*` form. Unlike the direct-Anthropic-SDK case (see `anthropic/openinference`'s README), this hits *both* input and output messages here, since `system` and user turns all go through the same array-shaped `content` field.

Worked around with hand-written `transform/fix_input_messages` / `transform/fix_output_messages` processors in [`otelcol-config.yaml`](otelcol-config.yaml) that rebuild both attributes from the raw `llm.*` attributes after `genainormalizer` runs (`remove_originals` is turned off, and `transform/cleanup_raw_attrs` strips the raw attributes afterward instead). This only handles the single `"text"`-type content block per message that `write_haiku` produces (`llm.input_messages.0` = system prompt, `.1` = user message, `llm.output_messages.0` = assistant reply) — multiple content blocks or a tool call would need a corresponding statement added, and would otherwise fall back to `genainormalizer`'s empty-parts version. Remove this workaround once the upstream fix is merged and available in the pinned collector image.

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
