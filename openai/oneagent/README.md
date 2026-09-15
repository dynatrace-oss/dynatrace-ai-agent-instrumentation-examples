# OpenAI + OneAgent Demo

Demonstrates tracing OpenAI SDK API calls with Dynatrace via OneAgent auto-instrumentation.

> **Prompt capture is opt-in** — The Python OpenAI sensor is fully supported, but `gen_ai.input.messages` / `gen_ai.output.messages` are only populated when the optional **Python OpenAI prompt capture** feature is enabled. Without it, spans are produced but the Prompts tab shows no content. See [Prompt capture and streaming](#prompt-capture-and-streaming).

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

Two separate things affect what this demo's spans contain. They are often confused for one another.

**1. Message content is gated by a OneAgent feature, not by app code.**

`gen_ai.input.messages` and `gen_ai.output.messages` stay empty until **Python OpenAI prompt capture** is enabled under Settings → OneAgent features. Restart the Python process after enabling it. No change to this app can substitute for that setting.

**2. This demo deliberately does not use `stream=True`.**

Under streaming, the SDK returns a chunk iterator rather than a completed response body, so OneAgent has no single response object to read `gen_ai.response.model` and token counts from. Those attributes become unreliable, which silently empties the model column and the cost dashboard's span-token tiles.

The request is therefore non-streaming, and the caller reads the completed message directly:

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "Write a haiku."}],
    max_completion_tokens=2000,
)
return response.choices[0].message.content or ""
```

If you adapt this demo to stream, expect `gen_ai.response.model` and `gen_ai.usage.*` to degrade. Sibling demos that stream (`openai/opentelemetry`, `openai/openinference`) can afford to because their instrumentation libraries reassemble the stream themselves — OneAgent does not.

**Keep `max_completion_tokens` high enough to finish the answer.** A low cap truncates the completion mid-sentence, and the truncated text is what lands in `gen_ai.output.messages`. This looks like an instrumentation bug but is a request parameter.

Full attribute-by-attribute coverage: [`test/e2e/sdk-analysis/openai-oneagent.md`](../../test/e2e/sdk-analysis/openai-oneagent.md).

## Smartscape service entity

OneAgent uses the `FastAPI(title=...)` parameter to assign a Smartscape SERVICE entity. Apps with the same title on the same host are merged into one entity, which pollutes the topology. Each oneagent demo sets a unique title matching its service name so that each service gets its own distinct SERVICE (and GENAI_SERVICE) entity in Smartscape.
