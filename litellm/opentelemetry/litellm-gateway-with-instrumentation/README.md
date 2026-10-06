# LiteLLM Proxy Gateway with OpenInference

This migrated example replaces Traceloop/OpenLLMetry with `openinference-instrumentation-litellm`, enables OTel GenAI semantic-convention emission, and sends traces through an explicit app-owned OTLP/HTTP exporter.

## Migration decisions

- **One LLM instrumentation path:** `LiteLLMInstrumentor` replaces `Traceloop.init(...)`. LiteLLM's `otel` success/failure callbacks are removed to prevent duplicate LLM spans.
- **Explicit exporter:** the app exports traces to a local Collector at `COLLECTOR_BASE_URL`.
- **GenAI attributes:** `TraceConfig(enable_genai_semconv=True)` emits `gen_ai.*` alongside OpenInference fields.
- **Legacy cleanup:** the Collector maps required values first, then removes `llm.*` and `openinference.*` before Dynatrace ingest.
- **Content capture:** prompts and completions are intentionally captured. Review this before production because content can contain sensitive data.
- **Metrics:** OpenInference emits no metrics; the Collector derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` from LLM spans.

References: [Dynatrace OpenInference guidance](https://docs.dynatrace.com/docs/observe/dynatrace-for-ai-observability/get-started/openinference), [OpenInference LiteLLM instrumentation](https://arize-ai.github.io/openinference/python/instrumentation/openinference-instrumentation-litellm/), and the [source example](https://github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples/tree/main/litellm/opentelemetry/litellm-gateway-with-instrumentation).

## Prerequisites

- Python 3.10-3.14 and `uv`
- Docker and Ollama, with `llama3.2` and `all-minilm` pulled
- Optional Anthropic API key
- Dynatrace OTLP trace ingest
- Classic token with `openTelemetryTrace.ingest`; adapt authorization for a platform token
- Collector distribution containing `genainormalizer`, such as Dynatrace Collector 0.53.1+

## Configure

```bash
cp .env.example .env
# Edit .env without committing credentials.
set -a
source .env
set +a
```

`DT_ENDPOINT` is the environment base URL without `/api/v2/otlp`.

## Start the Collector

The shared [`otel-collector-config.yaml`](../otel-collector-config.yaml) fills `gen_ai.*` gaps from OpenInference's legacy attributes, then drops `llm.*`/`openinference.*`, and derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` from LLM spans. It needs the [Bindplane Distro for OpenTelemetry](https://github.com/observIQ/bindplane-otel-collector) for the `signal_to_metrics` connector. `make run` starts it for you; to start it by hand from `litellm/opentelemetry`:

```bash
docker run --rm \
  -p 127.0.0.1:4317:4317 \
  -p 127.0.0.1:4318:4318 \
  -v "$(pwd)/otel-collector-config.yaml:/etc/otelcol/otel-collector-config.yaml:ro" \
  -e DT_ENDPOINT \
  -e DT_API_TOKEN \
  ghcr.io/observiq/bindplane-agent:1.108.0 \
  --config=/etc/otelcol/otel-collector-config.yaml
```

## Run

```bash
uv sync
uv run python basic.py
```

The proxy is at `http://localhost:8000`; Admin UI is at `http://localhost:8000/ui`. Use `call_models.http` to send test requests. Generate and commit the lockfile with `uv lock`.

## Validate

After one successful request and clean Collector logs:

```bash
dtctl version
dtctl config current-context
dtctl auth whoami --plain

dtctl wait query 'fetch spans, from: now()-10m
  | filter service.name == "litellm-gateway"
  | filter isNotNull(gen_ai.request.model)
  | limit 1' --for=count=1 --timeout 5m -o json --plain

dtctl query 'fetch spans, from: now()-30m
  | filter service.name == "litellm-gateway"
  | filter isNotNull(gen_ai.request.model)
  | summarize spans = count(),
      response_model = countIf(isNotNull(gen_ai.response.model)),
      input_tokens = countIf(isNotNull(gen_ai.usage.input_tokens) or isNotNull(gen_ai.usage.prompt_tokens)),
      output_tokens = countIf(isNotNull(gen_ai.usage.output_tokens) or isNotNull(gen_ai.usage.completion_tokens)),
      provider_id = countIf(isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)),
      by:{gen_ai.operation.name}' -o json --plain
```

For inference operations, field counts should equal `spans`. Inspect mapped request fields:

```dql
fetch spans, from: now()-30m
| filter service.name == "litellm-gateway"
| filter isNotNull(gen_ai.request.model)
| fields timestamp, span.name,
    gen_ai.operation.name,
    gen_ai.provider.name,
    gen_ai.request.model,
    gen_ai.response.model,
    gen_ai.request.temperature,
    gen_ai.request.top_p,
    gen_ai.request.max_tokens,
    gen_ai.usage.input_tokens,
    gen_ai.usage.output_tokens
| sort timestamp desc
| limit 50
```

Verify legacy fields were removed; this query should return `0`:

```dql
fetch spans, from: now()-30m
| filter service.name == "litellm-gateway"
| filter isNotNull(llm.model_name) or isNotNull(openinference.span.kind)
| summarize legacy_spans = count()
```

Expected: provider identity, models, operation, and token usage are populated on successful inference spans; supplied request parameters are populated; `legacy_spans` is zero; message content is present by explicit choice.

Guardrail visibility is not implemented. An OpenInference `GUARDRAIL` span kind alone is not a standardized fired/blocked result.

## Baseline and rollback

Before deployment, record span volume and fields, dashboards/queries consuming Traceloop or legacy attributes, dependency versions, environment variables, exporter endpoints, and the rollback commit.

To roll back: stop this gateway and Collector config; restore the prior commit with `traceloop-sdk`, `Traceloop.init(...)`, and the previous Collector setup; restore affected queries; send a test request and compare with the baseline. Never run Traceloop and OpenInference LiteLLM instrumentation together in one process.
