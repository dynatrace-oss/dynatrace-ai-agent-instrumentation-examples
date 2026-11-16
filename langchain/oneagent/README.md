# LangChain + OneAgent (Gemini and Claude)

This sample traces LangChain chat models with Dynatrace using **OneAgent auto-instrumentation** only. No OpenTelemetry SDK or collector is involved.

OneAgent's LangChain sensor records the call structure. Model and token usage come from the provider SDK sensors underneath LangChain:

| LangChain model | Provider SDK | OneAgent sensor |
|---|---|---|
| `ChatGoogleGenerativeAI` (`langchain-google-genai`) | `google-genai` | Google GenAI |
| `ChatAnthropic` (`langchain-anthropic`) | `anthropic` | Anthropic |

> The Google GenAI and Anthropic sensors are experimental. Enable them in your Dynatrace settings, otherwise spans show the LangChain structure without model or token attributes.

The same sensors cover the Vertex AI variants (`ChatGoogleGenerativeAI` with `vertexai=True`, `ChatAnthropicVertex`), because those use the same `google-genai` and `anthropic` SDKs with a different endpoint.

## What this sample does

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body)
- Asks Gemini for a haiku, and Claude too when `ANTHROPIC_API_KEY` is set

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Dynatrace OneAgent installed on the host, with the Google GenAI and Anthropic sensors enabled
- A Gemini API key; optionally an Anthropic API key

## Environment

```env
GOOGLE_API_KEY=...
# Optional
ANTHROPIC_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite
CLAUDE_MODEL=claude-haiku-5-5
```

## Install and run

```bash
cd langchain/oneagent
make install
make run
```

Then in a second terminal:

```bash
make request
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies via uv |
| `make run` | Start the FastAPI app on port 8000 |
| `make request` | POST /haiku with a sample topic |
| `make build` / `make push` | Build / push the container image |

## Dynatrace views

Open the **AI Observability** app and filter by `service.name = langchain/oneagent` to see the model, token usage, and latency for each call.
