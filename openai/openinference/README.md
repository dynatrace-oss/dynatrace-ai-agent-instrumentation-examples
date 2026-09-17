# OpenAI with OpenInference GenAI semantic-convention dual-write

This separate Python example instruments the standard OpenAI client with OpenInference and sends OTLP/HTTP traces directly to Dynatrace.

It does not replace `openai/openinference/`. That example demonstrates normalization through a collector or Dynatrace OpenPipeline. This example instead uses OpenInference's opt-in GenAI semantic-convention dual-write support.

## Required compatibility setting

```bash
OPENINFERENCE_ENABLE_GENAI_SEMCONV=true
```

The setting makes OpenInference emit OpenTelemetry `gen_ai.*` attributes alongside its native `openinference.*` and `llm.*` attributes. It defaults to `false`. Without it, direct exports do not meet the Dynatrace AI Observability span contract unless a normalizer is applied.

The application fails fast when the setting is absent or not `true`.

## Prerequisites

- Python 3.10+
- An OpenAI API key
- A model available to that API key
- A Dynatrace access token with `openTelemetryTrace.ingest`

## Setup and run

```bash
cp .env.sample .env
# Fill in .env without committing it.
make install  # uv sync reads pyproject.toml
make run      # uv run --no-sync python app.py
```

The exporter sends traces to `${DT_ENDPOINT}/api/v2/otlp/v1/traces` with this header:

```text
Authorization: Api-Token ${DT_API_TOKEN}
```

## Privacy

Prompt and completion content can contain personal data, source code, or secrets. Content export remains disabled by default:

```bash
OPENINFERENCE_HIDE_INPUTS=true
OPENINFERENCE_HIDE_OUTPUTS=true
```

Do not change these values without an explicit data-governance decision.

## Validate

After one successful request, query the emitted spans in Dynatrace:

```dql
fetch spans
| filter service.name == "openai-openinference-genai-semconv"
| fields timestamp, trace.id, span.id, span.name,
    gen_ai.provider.name, gen_ai.operation.name,
    gen_ai.request.model, gen_ai.response.model,
    gen_ai.usage.input_tokens, gen_ai.usage.output_tokens,
    gen_ai.conversation.id
| sort timestamp desc
```

Check the result against the AI Observability contract. At minimum, verify:

- `gen_ai.provider.name` or deprecated `gen_ai.system`
- `gen_ai.operation.name`
- `gen_ai.request.model`
- `gen_ai.response.model`
- token-usage attributes when the response supplies usage

Record missing fields as compatibility gaps; do not silently synthesize them.

## Versions checked

Checked 2026-09-16:

- `openai==3.14.1`
- `openinference-instrumentation-openai==0.1.60`
- `openinference-instrumentation==0.1.61`
- `opentelemetry-sdk==1.44.0`
- `opentelemetry-exporter-otlp-proto-http==1.44.0`

Dependencies are declared in `pyproject.toml`; `requirements.txt` is intentionally not used.
