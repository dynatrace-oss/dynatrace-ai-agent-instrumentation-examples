## Google Agent Development Kit (ADK) + OpenTelemetry

Demonstrates tracing a multi-agent Google ADK application with Dynatrace via Traceloop (OpenLLMetry). The app exposes an academic research agent (`POST /research`) that coordinates two sub-agents — one for web search and one for suggesting new research directions. Spans carry `gen_ai.system = google_generativeai`.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Google AI Studio API key (`aistudio.google.com/apikey`)
- Dynatrace environment with API token

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install` — install dependencies
3. `make run` — start the app on port 8000
4. `make request` — send a test research request (in a second terminal)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | — | Google AI Studio API key (`aistudio.google.com/apikey`) |
| `MODEL` | No | `gemini-3.1-flash-lite` | Gemini model to use |
| `DT_API_TOKEN` | Yes | — | Dynatrace API token (ingest scope) |
| `OTEL_ENDPOINT` | Yes | — | Dynatrace OTLP endpoint (`https://<env>.live.dynatrace.com/api/v2/otlp`) |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run app locally on port 8000 |
| `make request` | POST /research to localhost:8000 |
| `make help` | Show all available targets |

## Dynatrace Instrumentation

Traceloop's OpenLLMetry SDK auto-instruments the Gemini SDK calls made by Google ADK:

```python
from traceloop.sdk import Traceloop

Traceloop.init(
    app_name="google-adk-samples",
    api_endpoint=os.environ["OTEL_ENDPOINT"],
    headers={"Authorization": f"Api-Token {os.environ['DT_API_TOKEN']}"},
    disable_batch=True,
)
```

> [!TIP]
> For detailed setup instructions and token scopes, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).
