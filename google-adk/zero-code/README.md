## Google Agent Development Kit (ADK) + zero-code OpenTelemetry

Demonstrates tracing and metering a multi-agent Google ADK application with Dynatrace **without any OpenTelemetry code in the application**. The app is identical to the [`google-adk/opentelemetry`](../opentelemetry) example except that it contains no tracer or meter provider setup: it runs under `opentelemetry-instrument`, and everything is configured through environment variables.

Use this variant when instrumentation has to be rolled out across many agents at once. The exporter endpoint, semantic-convention opt-ins, and content capture become deployment configuration (Terraform, Helm, a shared base image) instead of a code change in every agent repository.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Google AI Studio API key (`aistudio.google.com/apikey`)
- Dynatrace environment with API token

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install`; install dependencies
3. `make run-collector`; start the collector, then the app on port 8000 under `opentelemetry-instrument`
4. `make request`; send a test research request (in a second terminal)

`make run` exports straight to Dynatrace without the collector. Use it to see the raw ADK attributes; the Prompts view stays empty, for the reason described below.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | None | Google AI Studio API key (`aistudio.google.com/apikey`) |
| `MODEL` | No | `gemini-3.1-flash-lite` | Gemini model to use |
| `DT_API_TOKEN` | Yes | None | Dynatrace API token with `openTelemetryTrace.ingest` and `metrics.ingest` scopes |
| `OTEL_ENDPOINT` | Yes | None | Dynatrace OTLP endpoint (`https://<env>.live.dynatrace.com/api/v2/otlp`) |

The `Makefile` derives the standard `OTEL_*` variables from `OTEL_ENDPOINT` and `DT_API_TOKEN`. Override any of them from the environment to point at a collector or gateway instead.

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 under `opentelemetry-instrument`, exporting directly to Dynatrace |
| `make run-collector` | Start the collector, then run the app exporting through it |
| `make stop` | Stop and remove the collector container |
| `make logs` | Tail collector logs |
| `make request` | POST /research to localhost:8000 |
| `make help` | Show all available targets |

## Dynatrace Instrumentation

`opentelemetry-instrument` (from `opentelemetry-distro`) builds the SDK providers from environment variables before the application module is imported, then monkey-patches installed instrumentation libraries. Two consequences matter here:

- ADK creates its metric instruments at module import time, so the meter provider must exist first. Under `opentelemetry-instrument` it always does. The in-code variant has to set the provider before `import google.adk` by hand.
- `opentelemetry-instrumentation-fastapi` produces the `SERVER` span at the HTTP entry point. All of ADK's own spans are `span.kind = internal`, so without an entry-point instrumentation there is no span from which a service can be detected.

The full configuration:

```bash
OTEL_SERVICE_NAME=google-adk-zero-code
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=none
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=https://<env>.live.dynatrace.com/api/v2/otlp
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token <token>"
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta
OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=SPAN_ONLY
```

```bash
opentelemetry-instrument python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Notes on individual settings:

- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` is required; the Python default is gRPC, which the Dynatrace `/api/v2/otlp` endpoint does not serve.
- `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` is required; Dynatrace rejects cumulative OTLP metrics with HTTP 400.
- `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` must keep content on spans (`SPAN_ONLY` or `SPAN_AND_EVENT`). Dynatrace reads `gen_ai.input.messages` and `gen_ai.output.messages` as span attributes; `EVENT_ONLY` puts them in log events, where the AI Observability app cannot see them.
- `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` opts ADK and the Google GenAI SDK into current `gen_ai.*` semantics.

### Instrumentation packages are pinned explicitly

`pyproject.toml` lists the instrumentation packages by name rather than relying on `opentelemetry-bootstrap -a install`. Auto-detection would also install `opentelemetry-instrumentation-google-genai`, which wraps `generate_content` underneath ADK's own `call_llm` span. ADK already emits the `gen_ai.*` model attributes, so the extra instrumentation adds a second span for the same call. If it arrives transitively, disable it:

```bash
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google_genai,vertexai
```

The same reasoning rules out layering OpenLLMetry or OpenInference on top of ADK: both attach to the active tracer provider and re-instrument calls ADK has already traced.

### What the raw ADK attributes look like

Because nothing normalizes the telemetry on the way in, this example shows what ADK actually emits. Verified against a tenant:

| Attribute | `call_llm` span | child `generate_content <model>` span |
|---|---|---|
| `gen_ai.provider.name` / `gen_ai.system` | `gcp.vertex.agent` | absent |
| `gen_ai.request.model` | set | set |
| `gen_ai.usage.input_tokens` / `output_tokens` | set | set |
| `gen_ai.operation.name` | absent | `generate_content` |
| `gen_ai.input.messages` / `gen_ai.output.messages` | absent | set |
| `gen_ai.response.model` | absent | absent |

### Why the collector is not optional here

Every GenAI view in the AI Observability app admits a span only if `gen_ai.system` or `gen_ai.provider.name` is set, and the Prompts stream then drops rows that have neither input nor output. Against the table above, on a direct export:

- `call_llm` passes the first gate and is dropped by the second: it has a provider but no message content.
- `generate_content <model>` has the content but fails the first gate: neither provider field is set.

No ADK span satisfies both conditions, so **spans appear in Distributed Tracing while the Prompts view stays empty**. This is not a partial result that improves with more environment variables; it is zero prompts until something adds a provider to the content-bearing span.

`otel-collector-config.yaml` does that in two OTTL statements: set `gen_ai.provider.name` on any span that has a request model but no provider and no `gen_ai.system` (which is exactly the `generate_content` span, and leaves `call_llm` alone), and mirror `gen_ai.request.model` into `gen_ai.response.model`. In a Dynatrace-native deployment the same two statements are an OpenPipeline processor behind a `gen_ai.operation.name == "generate_content"` matcher.

Three things to know when reading this in Dynatrace:

- ADK opens **two nested spans per LLM call** (`call_llm`, and a child `generate_content <model>`), both from `google/adk/telemetry/tracing.py`. This is ADK's own span model, not double instrumentation.
- The semantic attributes are **split across those two spans**: provider identity and token counts sit on `call_llm`, message content sits on the child. Looking at either span alone shows a partial picture.
- `gen_ai.provider.name` is `gcp.vertex.agent`, not one of the spec's provider values, and `gen_ai.response.model` is on neither span (ADK records the response model only as a metric attribute).

None of this is reachable from environment variables; normalization has to happen in a collector or in OpenPipeline. The [`google-adk/opentelemetry`](../opentelemetry) example applies the same two statements and additionally derives `gen_ai.invoke_agent.duration` and `gen_ai.execute_tool.duration` with `span_metrics` connectors, which this config deliberately leaves out.

### Vertex AI / Gemini Enterprise

This example uses an AI Studio API key so it can run unattended in CI. For Vertex AI, drop `GOOGLE_API_KEY` and add:

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOCATION=<gcp-region>
```

On the managed Agent Engine runtime the container command is not yours to set, so `opentelemetry-instrument` is unavailable; there you need a small bootstrap module imported before `google.adk`, as in the [`google-adk/opentelemetry`](../opentelemetry) example.

> [!TIP]
> For detailed setup instructions and token scopes, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).
