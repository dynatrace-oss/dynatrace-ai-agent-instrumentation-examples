# Google ADK + OpenInference + Dynatrace AI Observability

Instrument a [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) agent that runs on Gemini with OpenInference, and send traces to Dynatrace AI Observability.
Uses [`openinference-instrumentation-google-adk`](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-google-adk) to auto-instrument ADK, and a [Bindplane OTel collector](https://github.com/observIQ/bindplane-agent) with the `genainormalizer` processor to translate OpenInference attributes to Dynatrace `gen_ai.*` format.

For the native ADK OpenTelemetry instrumentation of the same agent, see [`../opentelemetry`](../opentelemetry/).

---

## What you'll build

- Runs a FastAPI server exposing `POST /research` (accepts a `{"topic": "..."}` body).
- Runs the ADK academic research coordinator (`LlmAgent` on Gemini) that delegates to a web search sub-agent and a new research sub-agent through `AgentTool`.
- Produces OpenTelemetry traces with OpenInference and opt-in OTel GenAI semantic conventions (agent, LLM, and tool spans).
- Routes traces through a local Bindplane collector that normalizes `llm.*` attributes to `gen_ai.*`, and derives `gen_ai.client.operation.duration` and `gen_ai.client.token.usage` metrics from the LLM spans.

---

## Prerequisites

- A Dynatrace tenant (start a free trial at https://dt-url.net/trial)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker (to run the Bindplane collector)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

---

## Setup

1. Create a Dynatrace access token with the `openTelemetryTrace.ingest` and `metrics.ingest` scopes.
2. Copy `.env.sample` to `.env` and fill in the values:

   ```bash
   DT_ENDPOINT=https://abc12345.live.dynatrace.com
   DT_API_TOKEN=dt0c01.****.*****
   GOOGLE_API_KEY=...
   MODEL=gemini-3.1-flash-lite
   ```

3. Install dependencies:

   ```bash
   make install
   ```

---

## Run the example

```bash
make run       # starts the collector, then the app on port 8000
make request   # in a second terminal: POST /research
make stop      # stop the collector
```

Run `make help` for all targets.

---

## Visualize in Dynatrace AI Observability

Open the [AI Observability app](https://docs.dynatrace.com/docs/shortlink/app-ai-observability) and filter by service `google-adk/openinference`. Each request shows the agent, LLM, and tool spans with model name, token usage, and message content.

---

## How it works

`app.py` registers `GoogleADKInstrumentor` with `TraceConfig(enable_genai_semconv=True)` before ADK runs, and exports spans over OTLP HTTP to the endpoint in `OTEL_EXPORTER_OTLP_ENDPOINT` (`make run` points it at the local collector).

`otel-collector-config.yaml` uses the `gen_ai_normalizer` processor with the `openinference` source to map OpenInference attributes to `gen_ai.*`, copies `gen_ai.request.model` to `gen_ai.response.model`, and derives the GenAI client metrics from LLM spans with the `span_metrics` and `signal_to_metrics` connectors.

---

## Troubleshooting

- No traces: confirm the collector is running with `docker ps | grep google-adk-openinference-otel-collector` and check `make logs`.
- Port 4318 already in use: stop any other local collector first.
- `502 agent model error`: Gemini rejected the call (quota, safety, or recitation). The app retries up to three times on a fresh session.
