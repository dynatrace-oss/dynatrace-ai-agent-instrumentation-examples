# Langfuse OpenTelemetry — Node.js

Node.js/TypeScript demo: makes an OpenAI haiku call and emits a span with the
**Langfuse 4.x OTel attribute schema** (`langfuse.observation.*`). The OTel Collector
(or Dynatrace OpenPipeline) transforms those attributes to `gen_ai.*`, producing the
same result in Dynatrace AI Observability as the Python sibling demo.

This demo mirrors [`../opentelemetry/`](../opentelemetry/) (Python) and shares the same
collector config (`../opentelemetry/otel-collector-config.yaml`).

> **Why manual spans instead of the Langfuse SDK?**
> The Langfuse Node.js SDK (3.x, latest on npm) sends data to the Langfuse server
> directly and does not yet support OTel export. The Python SDK 4.x added this support.
> This demo manually emits `langfuse.observation.*` OTel attributes using
> `@opentelemetry/api`, demonstrating the same pipeline until the Node.js SDK catches up.

## Prerequisites

- Node.js 20+
- Docker (for the collector path)
- OpenAI or Azure OpenAI API credentials
- Dynatrace tenant with an API token (`openTelemetryTrace.ingest` + `metrics.ingest` scopes)

## Quick start

```bash
cp .env.sample .env
# Edit .env with your credentials

make install
make run           # collector path — transforms langfuse.* → gen_ai.* locally
# OR
make run-openpipeline   # direct to Dynatrace — OpenPipeline transforms on ingestion
```

## How it works

1. `initTelemetry()` sets up `NodeSDK` with `OTLPTraceExporter` (reads `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` from env).
2. A single OTel span is emitted with `langfuse.observation.type`, `langfuse.observation.model.name`, `langfuse.observation.usage_details` (JSON), and `langfuse.observation.input/output`.
3. The OTel Collector (or Dynatrace OpenPipeline) transforms `langfuse.*` → `gen_ai.*`.
4. Spans appear in Dynatrace AI Observability with model name, token usage, and latency.

### Collector path (`make run`)

```
Node.js app → OTLP → OTel Collector → (transform) → Dynatrace
```

Collector config: `../opentelemetry/otel-collector-config.yaml`

### OpenPipeline path (`make run-openpipeline`)

```
Node.js app → OTLP → Dynatrace → (OpenPipeline: langfuse.* → gen_ai.*)
```

Requires the processors from `../opentelemetry/openpipeline-langfuse.yaml` to be deployed.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DT_ENDPOINT` | yes | Dynatrace tenant URL |
| `DT_API_TOKEN` | yes | API token with ingest scopes |
| `OPENAI_API_KEY` | yes | OpenAI or Azure OpenAI key |
| `OPENAI_API_BASE` | no | Override OpenAI base URL (or Azure endpoint) |
| `OPENAI_API_VERSION` | no | Azure OpenAI API version (activates Azure client) |
| `MODEL` | no | Model/deployment name (default: `gpt-4o-mini`) |
| `TOPIC` | no | Haiku topic (default: `observability`) |
