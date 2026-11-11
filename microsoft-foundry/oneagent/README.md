# Microsoft Foundry + OneAgent Demo

Demonstrates tracing Microsoft Foundry Agent Service calls made with the `azure-ai-projects` Python SDK, using Dynatrace OneAgent auto-instrumentation.

> **Experimental sensor**: the OneAgent Foundry sensor instruments the Foundry agent management API (creating agent versions, sessions, memory search, routine dispatch). It does not capture prompts or responses of model calls; model calls made through `project_client.get_openai_client()` are covered by the OneAgent OpenAI sensor instead.

## What the sensor captures

The demo calls `client.agents.create_version(...)` on every `POST /haiku`. OneAgent records a span with:

| Attribute | Value |
|-----------|-------|
| `gen_ai.provider.name` | `microsoft.foundry` |
| `gen_ai.operation.name` | `create_agent` |
| `gen_ai.agent.name` | `AGENT_NAME` |
| `gen_ai.request.model` | `MODEL` |
| `gen_ai.request.temperature`, `gen_ai.request.top_p` | from the agent definition |
| `gen_ai.agent.id`, `gen_ai.agent.version` | from the response |
| `gen_ai.response.model` | from the response |
| `server.address`, `server.port` | from the project endpoint |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Microsoft Foundry project and its endpoint (`https://<resource>.services.ai.azure.com/api/projects/<project>`)
- A model deployment in that project (`MODEL`)
- Microsoft Entra ID credentials picked up by `DefaultAzureCredential` (`az login`, or `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET`). Foundry projects do not accept Azure OpenAI API keys for the agents API.
- Dynatrace OneAgent **1.345 or later** installed on the host

## Enable the OneAgent feature

The sensor is off by default. In Dynatrace, go to **Settings** > **Preferences** > **OneAgent features**, search for `Microsoft Foundry`, and turn on **Experimental Python GenAI Microsoft Foundry [Opt-In]**. Restart the app afterwards. There is no prompt capture variant of this feature.

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your values
2. `make install` (install dependencies)
3. `make run` (start the app on port 8000)
4. `make request` (send a test request, in a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_AI_PROJECT_ENDPOINT` | Yes | (none) | Foundry project endpoint |
| `MODEL` | No | `gpt-4o-mini` | Model deployment name used in the agent definition |
| `AGENT_NAME` | No | `haiku-agent` | Agent name; each request creates a new version |
| `FOUNDRY_STATIC_TOKEN` | No | (none) | Fixed bearer token instead of `DefaultAzureCredential`; only for the e2e mock |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make build` | Build container image (`APP_IMAGE`, `BUILD_PLATFORM`) |
| `make push` | Build and push image to registry |
| `make request` | POST /haiku to localhost:8000 |
| `make help` | Show all available targets |

## Screenshots

See [`assets/`](./assets/). Screenshots are not captured yet.

## Smartscape service entity

OneAgent uses the `FastAPI(title=...)` parameter to assign a Smartscape SERVICE entity. Each oneagent demo sets a unique title matching its service name so that each service gets its own SERVICE (and GENAI_SERVICE) entity.
