# Azure OpenAI with OpenInference GenAI semantic conventions

This Python example instruments the Azure OpenAI client with OpenInference and sends OTLP/HTTP traces directly to Dynatrace.

## Important compatibility setting

Set `OPENINFERENCE_ENABLE_GENAI_SEMCONV=true`.

This setting is required for this direct-export recipe. It makes OpenInference emit OpenTelemetry `gen_ai.*` semantic-convention attributes alongside its native `openinference.*` and `llm.*` attributes. Without it, the spans are valid OpenTelemetry spans, but their OpenInference attributes do not satisfy the Dynatrace AI Observability query contract without normalization.

The upstream default is `false`. The example fails fast if the setting is absent or false instead of silently exporting incompatible spans.

## Prerequisites

- Python 3.10+
- An Azure OpenAI resource and deployed model
- The Azure endpoint, API key, deployment name, and supported API version
- A Dynatrace access token with `openTelemetryTrace.ingest`

## Run

1. Copy `.env.sample` to `.env` and fill in the values without committing it.
2. Create a Python virtual environment and install the pinned packages from `requirements.txt`.
3. Run `make run`.

The exporter sends traces to `${DT_ENDPOINT}/api/v2/otlp/v1/traces` with the `Authorization: Api-Token ${DT_API_TOKEN}` header.

## Privacy

Prompt and completion content can contain source code, personal data, and secrets. This example keeps content hidden by default with `OPENINFERENCE_HIDE_INPUTS=true` and `OPENINFERENCE_HIDE_OUTPUTS=true`. Do not disable these settings without an explicit data-governance decision.

## Validate

After one successful request, query spans in Dynatrace:

```dql
fetch spans
| filter service.name == "azure-openai-openinference"
| fields timestamp, trace.id, span.id, span.name,
    gen_ai.provider.name, gen_ai.operation.name,
    gen_ai.request.model, gen_ai.response.model,
    gen_ai.usage.input_tokens, gen_ai.usage.output_tokens,
    gen_ai.conversation.id
| sort timestamp desc
```

Verify that the span has `gen_ai.provider.name` (or deprecated `gen_ai.system`), `gen_ai.operation.name`, request and response model attributes, and token usage. Record any missing field as a compatibility gap rather than synthesizing it silently.

## Versions checked

Checked 2026-09-16:

- `openinference-instrumentation-openai==0.1.60`
- `openinference-instrumentation==0.1.61`
- `openai==3.14.1`
- `opentelemetry-sdk==1.44.0`
- `opentelemetry-exporter-otlp-proto-http==1.44.0`
