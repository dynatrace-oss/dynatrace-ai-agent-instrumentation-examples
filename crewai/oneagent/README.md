# CrewAI + OneAgent Demo

Demonstrates tracing a CrewAI crew (one "Poet" agent, one task) against Azure OpenAI with Dynatrace via OneAgent auto-instrumentation. The app contains no OpenTelemetry code: every span comes from OneAgent.

## Prerequisites

- Python 3.11–3.13 (CrewAI 1.15.41 does not support 3.14+)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Azure OpenAI resource (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`)
- Dynatrace OneAgent 1.339+ installed on the host

### Enable the OneAgent features

Settings → OneAgent features, then restart the Python process:

| Feature | Why |
|---------|-----|
| Experimental Python GenAI CrewAI (OneAgent 1.339+) | `workflow`, `task` and `agent` spans |
| Python GenAI OpenAI | the `chat` span for the model call |
| Python GenAI OpenAI prompt capture | `gen_ai.input.messages` on the chat span |
| Python GenAI OpenAI guardrails capture | `gen_ai.guardrail.*` attributes |

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install` — install dependencies
3. `make run` — start the app on port 8000
4. `make request` — send a test haiku request (in a second terminal)
5. `make request-guardrail` — send a prompt that trips the Azure content filter

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | — | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Yes | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | No | `genai-demo` | Azure deployment name |
| `OPENAI_API_VERSION` | No | — | Set it when running the e2e suite so the guardrail request is sent |
| `GUARDRAIL_PROMPT` | No | jailbreak prompt | Prompt `/haiku-guardrail` sends; tune it to your filter configuration |

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

## What to check in AI Observability

Each `POST /haiku` produces one trace:

```
workflow   (CrewAI sensor, with token usage)
  task     (CrewAI sensor)
    agent  (CrewAI sensor)
      chat (OpenAI sensor, with input messages)
```

The e2e suite `TestCrewAIOneAgent` asserts each of these spans, and that the chat span's input messages contain the request topic.

## How the model is reached

CrewAI's native OpenAI provider is forced with `custom_openai=True` and pointed at Azure's `/openai/v1/` endpoint, so the call goes through `openai.OpenAI` and the OneAgent OpenAI sensor produces the chat span. `stream=False` is set explicitly because the sensor does not reassemble streamed chunks.

Non-native CrewAI models (and `is_litellm=True`) route through LiteLLM instead and need the OneAgent LiteLLM feature; see [`litellm/oneagent`](../../litellm/oneagent/).

## Guardrails

`POST /haiku-guardrail` runs the crew with `GUARDRAIL_PROMPT` so the Azure OpenAI content filter intervenes. The endpoint catches the resulting CrewAI exception and still returns 200. OneAgent only writes `gen_ai.guardrail.input.content` / `gen_ai.guardrail.output.content` when the filter actually fires, so tune the prompt to the categories configured on your deployment and enable the guardrails capture feature. The e2e audit skips, rather than fails, when no guardrail attribute is found. See [`openai/oneagent`](../../openai/oneagent/) for the full attribute list.

## Limits

- The chat span carries a `gen_ai.conversation.id` that the sensor generates per call (a different UUID for each request). It is not tied to any id the app supplies, so don't use it to group multi-turn conversations. The demo is single-turn.
- The CrewAI sensor is experimental and its schema may change.
