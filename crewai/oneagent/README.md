# CrewAI + OneAgent

This sample traces a [CrewAI](https://docs.crewai.com/) crew with Dynatrace using **OneAgent auto-instrumentation**, with no OpenTelemetry code or collector. OneAgent's CrewAI sensor ships the orchestration spans straight to Dynatrace.

## What this sample does

- Runs a FastAPI server with `POST /haiku` (accepts a `{"topic": "..."}` body), which kicks off a one-agent crew against Azure OpenAI
- Exposes `POST /chat` (`{"message": "...", "session_id": "..."}`), one turn of a conversational CrewAI Flow, so turns with the same `session_id` share a conversation
- Relies on the OneAgent CrewAI sensor for the `workflow`, `task` and `agent` spans

## Prerequisites

- Python 3.11 to 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Dynatrace OneAgent 1.339+ installed on the host
- An Azure OpenAI deployment

In Dynatrace, go to **Settings** > **OneAgent features** and turn on **Experimental Python GenAI CrewAI [Opt-In]**, then restart the Python process.

Prompt and guardrail capture need the Python OpenAI sensor features instead; see [`openai/oneagent`](../../openai/oneagent/).

## Environment

Copy `.env.sample` to `.env` and fill in the values:

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (default `genai-demo`) |

## Install and run

```bash
cd crewai/oneagent
make install
make run
```

Then in a second terminal:

```bash
make request        # single crew run
make request-chat   # two chat turns on one session
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies via uv |
| `make run` | Start the FastAPI app on port 8000 |
| `make request` | POST /haiku with a sample topic |
| `make request-chat` | POST two /chat turns with the same `session_id` |
| `make build` / `make push` | Build / push the container image |

## Dynatrace views

Open the **AI Observability** app and filter by `service.name = crewai/oneagent` to explore the workflow, task and agent spans.
