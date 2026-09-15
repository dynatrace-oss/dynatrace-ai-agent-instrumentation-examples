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

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make help` | Show all available targets |

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
