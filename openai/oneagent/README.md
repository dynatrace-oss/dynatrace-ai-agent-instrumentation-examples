# OpenAI + OneAgent Demo

Demonstrates tracing OpenAI SDK API calls with Dynatrace via OneAgent auto-instrumentation.

> **Streaming drops the output message** — OneAgent's Python OpenAI sensor does not reassemble streamed chunks, so `stream=True` leaves `gen_ai.output.messages` absent from the span. This demo uses non-streaming for that reason. Content additionally requires the optional **Python OpenAI prompt capture** feature. See [Prompt capture and streaming](#prompt-capture-and-streaming).

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- OpenAI API key (`OPENAI_API_KEY`)
- Dynatrace OneAgent installed on the host

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install` — install dependencies
3. `make run` — start the app on port 8000
4. `make request` — send a test haiku request (in a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `MODEL` | No | `gpt-4o` | Model to use |
| `OPENAI_API_BASE` | No | — | Custom API base URL (e.g. Azure OpenAI endpoint) |
| `OPENAI_API_VERSION` | No | — | API version (required for Azure OpenAI) |
| `GUARDRAIL_PROMPT` | No | prompt-injection attempt | Prompt `POST /haiku-guardrail` sends to trip the Azure content filter |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make request-guardrail` | POST /haiku-guardrail to localhost:8000 |
| `make help` | Show all available targets |

## Guardrails

`POST /haiku-guardrail` sends `GUARDRAIL_PROMPT` so the provider's content filter intervenes, which is what makes the guardrail views in AI Observability populate. Three things must all hold, or the span carries no guardrail attribute at all:

1. *The demo must target Azure OpenAI* (`OPENAI_API_BASE` + `OPENAI_API_VERSION`). OneAgent derives its guardrail attributes from Azure's `prompt_filter_results` / `content_filter_results` payloads and from the body of the `BadRequestError` Azure raises on a filtered prompt. `api.openai.com` returns none of those, so the endpoint still answers on plain OpenAI but produces no guardrail data.
2. *Enable the experimental guardrail capture feature.* Settings → OneAgent features → the GenAI `captureGuardrails` setting. It is *off by default* — with it off the sensor parses nothing and the attributes are absent even on a genuinely blocked request. Restart the Python process after enabling.
3. *The filter must actually fire.* OneAgent only writes guardrail attributes for a request the filter intervened on; a passing request carries nothing. Tune `GUARDRAIL_PROMPT` to the filter categories or custom blocklists configured on your deployment.

What OneAgent writes when it does fire:

| Attribute | Source |
|-----------|--------|
| `gen_ai.guardrail.input.content` | Prompt categories that tripped, e.g. `[{"type":"JAILBREAK"}]`, `[{"type":"HATE","confidence":"MEDIUM"}]` |
| `gen_ai.guardrail.output.content` | Same, for the completion |
| `gen_ai.guardrail.input.words.lists` / `.output.words.lists` | Names of matched custom blocklists |
| `gen_ai.guardrail.output.sensitive_information.piis` | PII sub-categories detected in the completion (Azure offers no input-side PII filter) |

These are *not* the `gen_ai.bedrock.guardrail.*` attributes, which only exist on the AWS Bedrock path, and *not* the raw `gen_ai.prompt.prompt_filter_results` / `gen_ai.completion.content_filter_results` blobs the OTel/OpenInference path emits — OneAgent-sourced spans never carry those.

A filtered prompt makes the span an error span (`span.status_code = "error"`, `gen_ai.response.finish_reasons = "content_filter"`) and drops token usage; a filtered completion does not. The endpoint catches both so it still returns 200.

## Prompt capture and streaming

**This demo deliberately does not use `stream=True`.**

OneAgent's Python OpenAI sensor reads the completed response object. Under streaming the SDK returns a chunk iterator instead, and the sensor does not reassemble it, so the response never reaches the span — `gen_ai.output.messages` is absent entirely, along with unreliable `gen_ai.response.model` and `gen_ai.usage.*`. Enabling prompt capture does not help here; there is no assembled response for it to capture.

Switching to non-streaming makes the output message appear:

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "Write a haiku."}],
    max_completion_tokens=2000,
)
return response.choices[0].message.content or ""
```

Sibling demos that stream (`openai/opentelemetry`, `openai/openinference`) can afford to because their instrumentation libraries reassemble the stream themselves. OneAgent does not. If you adapt this demo to stream, expect to lose the output message.

**Message content also requires the optional Python OpenAI prompt capture feature.** Enable it under Settings → OneAgent features and restart the Python process. This is necessary but not sufficient — with prompt capture on and streaming still enabled, `gen_ai.output.messages` remains empty.

**Keep `max_completion_tokens` high enough to finish the answer.** A low cap truncates the completion mid-sentence, and the truncated text is what lands in `gen_ai.output.messages`. This looks like an instrumentation bug but is a request parameter.

Full attribute-by-attribute coverage: [`test/e2e/sdk-analysis/openai-oneagent.md`](../../test/e2e/sdk-analysis/openai-oneagent.md).

## Smartscape service entity

OneAgent uses the `FastAPI(title=...)` parameter to assign a Smartscape SERVICE entity. Apps with the same title on the same host are merged into one entity, which pollutes the topology. Each oneagent demo sets a unique title matching its service name so that each service gets its own distinct SERVICE (and GENAI_SERVICE) entity in Smartscape.
