# CrewAI + OneAgent

This sample traces a [CrewAI](https://docs.crewai.com/) crew with Dynatrace using **OneAgent auto-instrumentation**, with no OpenTelemetry code or collector. OneAgent's CrewAI sensor ships the orchestration spans straight to Dynatrace.

## What this sample does

- Runs a FastAPI server with `POST /haiku` (accepts a `{"topic": "..."}` body), which kicks off a one-agent crew against Azure OpenAI
- Exposes `POST /chat` (`{"message": "...", "session_id": "..."}`), one turn of a chat: the app keeps the history per `session_id` and runs the crew again with it, so a turn can build on the earlier ones
- Relies on the OneAgent CrewAI sensor for the `workflow`, `task` and `agent` spans (each request and each chat turn is one crew run)

## Prerequisites

- Python 3.11 to 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Dynatrace OneAgent 1.339+ installed on the host
- An Azure OpenAI deployment

In Dynatrace, go to **Settings** > **OneAgent features** and turn on **Experimental Python GenAI CrewAI [Opt-In]**, then restart the Python process.

**Optional: capture prompts.** The app calls the model through CrewAI's native OpenAI provider (`custom_openai=True`), so enabling **Python GenAI OpenAI** and **Python GenAI OpenAI prompt capture** adds `openai.chat` spans with the prompts under the agent span. The CrewAI sensor does not need them and the e2e does not assert them. For guardrails see [`openai/oneagent`](../../openai/oneagent/).

The CrewAI sensor sets no `gen_ai.conversation.id`, so chat turns are separate traces and are not grouped by an attribute.

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
make request-chat   # two chat turns on one session, the second builds on the first
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
