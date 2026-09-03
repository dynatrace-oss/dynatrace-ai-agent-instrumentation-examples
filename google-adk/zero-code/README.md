## Google Agent Development Kit (ADK) + zero-code OpenTelemetry

Demonstrates tracing and metering a multi-agent Google ADK application with Dynatrace **without any application code at all**. This demo ships an agent package and nothing else: no tracer or meter provider setup, and no web server of its own. It runs ADK's own `adk api_server` under `opentelemetry-instrument`, and everything is configured through environment variables.

Use this variant when instrumentation has to be rolled out across many agents at once. The exporter endpoint, semantic-convention opt-ins, and content capture become deployment configuration (Terraform, Helm, a shared base image) instead of a code change in every agent repository. It matches what `adk deploy` produces for Cloud Run: a generated Dockerfile whose command is `adk api_server`, which you own and can prepend `opentelemetry-instrument` to.

The agent itself is the same academic research coordinator as the [`google-adk/opentelemetry`](../opentelemetry) example, restructured into the `agents/<app_name>/` layout ADK's server expects.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Google AI Studio API key (`aistudio.google.com/apikey`)
- Dynatrace environment with API token

## Quick Start

1. Copy `.env.sample` to `.env` and fill in your credentials
2. `make install`; install dependencies
3. `make run-collector`; start the collector, then ADK's server on port 8000 under `opentelemetry-instrument`
4. `make request`; create a session and send a test research request (in a second terminal)

`make run` exports straight to Dynatrace without the collector. Use it to see the raw ADK attributes; the Prompts view stays empty, for the reason described below.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | None | Google AI Studio API key (`aistudio.google.com/apikey`) |
| `MODEL` | No | `gemini-3.1-flash-lite` | Gemini model to use |
| `DT_API_TOKEN` | Yes | None | Dynatrace API token with `openTelemetryTrace.ingest` and `metrics.ingest` scopes |
| `OTEL_ENDPOINT` | Yes | None | Dynatrace OTLP endpoint (`https://<env>.live.dynatrace.com/api/v2/otlp`) |

The `Makefile` derives the standard `OTEL_*` variables from `OTEL_ENDPOINT` and `DT_API_TOKEN`. Override any of them from the environment to point at a collector or gateway instead.

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run ADK's API server on port 8000 under `opentelemetry-instrument`, exporting directly to Dynatrace |
| `make run-collector` | Start the collector, then run ADK's server exporting through it |
| `make stop` | Stop and remove the collector container |
| `make logs` | Tail collector logs |
| `make request` | Create a session and POST /run to ADK's server on localhost:8000 |
| `make help` | Show all available targets |

## Dynatrace Instrumentation

`opentelemetry-instrument` (from `opentelemetry-distro`) builds the SDK providers from environment variables before the application module is imported, then monkey-patches installed instrumentation libraries. Two consequences matter here:

- ADK creates its metric instruments at module import time, so the meter provider must exist first. Under `opentelemetry-instrument` it always does. The in-code variant has to set the provider before `import google.adk` by hand. ADK also tries to install its own tracer provider and logs `Overriding of current TracerProvider is not allowed`; that is expected and harmless, since the provider built from the environment is the one in use.
- `opentelemetry-instrumentation-fastapi` produces the `SERVER` span at the HTTP entry point. All of ADK's own spans are `span.kind = internal`, so without an entry-point instrumentation there is no span from which a service can be detected. `adk api_server` serves a FastAPI app (`google/adk/cli/api_server.py`), so this instruments ADK's own server; the demo contributes no web code. Verified: `GET /health` and `GET /list-apps` arrive as `SERVER` spans.

The full configuration:

```bash
OTEL_SERVICE_NAME=google-adk-zero-code
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=none
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=https://<env>.live.dynatrace.com/api/v2/otlp
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token <token>"
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta
OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=SPAN_ONLY
```

```bash
opentelemetry-instrument python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Notes on individual settings:

- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` is required; the Python default is gRPC, which the Dynatrace `/api/v2/otlp` endpoint does not serve.
- `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` is required; Dynatrace rejects cumulative OTLP metrics with HTTP 400.
- `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` must keep content on spans (`SPAN_ONLY` or `SPAN_AND_EVENT`). Dynatrace reads `gen_ai.input.messages` and `gen_ai.output.messages` as span attributes; `EVENT_ONLY` puts them in log events, where the AI Observability app cannot see them.
- `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` opts ADK and the Google GenAI SDK into current `gen_ai.*` semantics.

### Instrumentation packages are pinned explicitly

`pyproject.toml` lists the instrumentation packages by name rather than relying on `opentelemetry-bootstrap -a install`. Auto-detection would also install `opentelemetry-instrumentation-google-genai`, which wraps `generate_content` underneath ADK's own `call_llm` span. ADK already emits the `gen_ai.*` model attributes, so the extra instrumentation adds a second span for the same call. If it arrives transitively, disable it:

```bash
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google_genai,vertexai
```

The same reasoning rules out layering OpenLLMetry or OpenInference on top of ADK: both attach to the active tracer provider and re-instrument calls ADK has already traced.

### What the raw ADK attributes look like

Because nothing normalizes the telemetry on the way in, this example shows what ADK actually emits. Verified against a tenant:

| Attribute | `call_llm` span | child `generate_content <model>` span |
|---|---|---|
| `gen_ai.provider.name` / `gen_ai.system` | `gcp.vertex.agent` | absent |
| `gen_ai.request.model` | set | set |
| `gen_ai.usage.input_tokens` / `output_tokens` | set | set |
| `gen_ai.operation.name` | absent | `generate_content` |
| `gen_ai.input.messages` / `gen_ai.output.messages` | absent | set |
| `gen_ai.response.model` | absent | absent |

### Why the collector is not optional here

Every GenAI view in the AI Observability app admits a span only if `gen_ai.system` or `gen_ai.provider.name` is set, and the Prompts stream then drops rows that have neither input nor output. Against the table above, on a direct export:

- `call_llm` passes the first gate and is dropped by the second: it has a provider but no message content.
- `generate_content <model>` has the content but fails the first gate: neither provider field is set.

No ADK span satisfies both conditions, so **spans appear in Distributed Tracing while the Prompts view stays empty**. This is not a partial result that improves with more environment variables; it is zero prompts until something adds a provider to the content-bearing span.

`otel-collector-config.yaml` reconciles the two spans:

1. **Set `gen_ai.provider.name` to `vertexai` on the inference span.** The predicate is "has `gen_ai.operation.name` and `gen_ai.request.model`", which identifies `generate_content` uniquely: `call_llm` has the model but no operation name, and `invoke_agent` / `execute_tool` have the operation name but no model. Admitting those would inflate the app's LLM request count, which is `count()` over everything passing the gate. The value is `vertexai` rather than the semconv `gcp.vertex_ai` because the app keys its provider icons on the lowercased provider name and Smartscape mints `GENAI_PROVIDER` nodes from this string; `gemini` matches no icon key and creates an off-name topology node.
2. **Delete `gen_ai.system` and `gen_ai.provider.name` where either equals `gcp.vertex.agent`.** ADK writes its own instrumentation scope name into both (as of 2.8.0), and the app resolves the provider as `coalesce(gen_ai.system, gen_ai.provider.name)`. Left in place it surfaces as a provider entity literally named `gcp.vertex.agent`, and because `call_llm` carries a duplicate copy of the token counts, every token and every LLM request is counted twice. Both keys have to go: deleting one still leaves `call_llm` inside the gate through the other. Removing the attributes rather than the span keeps `call_llm` in the trace waterfall as the parent of `generate_content`. This runs before the backfill in step 1 so a future ADK release that sets the scope name on the inference span too cannot leave that span with no provider at all.
3. **Normalize a stray `gen_ai.system` of `vertex_ai` or `gemini`** on the span just tagged. Which library emits `generate_content` depends on the deployed image: with `google-adk[otel-gcp]` the `google-genai` instrumentation emits it and sets no `gen_ai.system` under the experimental opt-in, while without the extra ADK emits it and does set one. Since `gen_ai.system` outranks `gen_ai.provider.name`, a stray value means the same provider under two names, with two icons and two Smartscape nodes.
4. **Mirror `gen_ai.request.model` into `gen_ai.response.model`**, which ADK records only as a metric attribute.
5. **Drop `gcp.vertex.agent.llm_request` / `llm_response`**, ADK's own large duplicates of the semconv message attributes. Nothing in the app reads them.

Verified against a tenant: the `generate_content` span alone carries the messages, model, token counts, `gen_ai.agent.name`, `gen_ai.conversation.id` and `gen_ai.system_instructions`, so removing `call_llm` from the gate loses nothing.

In a Dynatrace-native deployment the same statements are an OpenPipeline processor behind a `gen_ai.operation.name == "generate_content"` matcher.

Three things to know when reading this in Dynatrace:

- ADK opens **two nested spans per LLM call** (`call_llm`, and a child `generate_content <model>`), both from `google/adk/telemetry/tracing.py`. This is ADK's own span model, not double instrumentation.
- The semantic attributes are **split across those two spans**: provider identity and token counts sit on `call_llm`, message content sits on the child. Looking at either span alone shows a partial picture.
- `gen_ai.provider.name` is `gcp.vertex.agent`, not one of the spec's provider values, and `gen_ai.response.model` is on neither span (ADK records the response model only as a metric attribute).

### span.kind and service detection

Every span ADK emits is `span.kind = internal`, so nothing in ADK's own output lets SDv2 detect a service. This example does not rewrite span kinds in the collector; it gets a genuine `SERVER` span from the `opentelemetry-instrumentation-fastapi` package that `opentelemetry-instrument` loads, wrapping ADK's own FastAPI server. That is the accurate fix and needs no pipeline rule, and it requires no application code, only the package in the image and `opentelemetry-instrument` in front of the command.

This works wherever you own the container command, which includes the Dockerfile `adk deploy` generates for Cloud Run. Where the runtime owns the entry point instead (a managed Agent Engine deployment), there is nothing to prepend `opentelemetry-instrument` to, and the option is to promote the **root** invocation span only, in the collector:

```yaml
- set(span.kind, SPAN_KIND_SERVER) where span.attributes["gen_ai.operation.name"] == "invoke_agent" and span.parent_span_id.string == ""
```

That is defensible because the root agent invocation genuinely is the entry point of a remotely triggered operation. Promoting every internal span is not: it invents entry points for each nested LLM call and tool execution.

None of this is reachable from environment variables; normalization has to happen in a collector or in OpenPipeline.

The config also derives the two spec-named agent metrics with `span_metrics` connectors: `gen_ai.invoke_agent.duration` and `gen_ai.execute_tool.duration`. ADK records equivalents under its own pre-semconv names (`gen_ai.agent.invocation.duration`, `gen_ai.tool.execution.duration`), which still flow through untouched; the connectors add the spec-named versions alongside them. Each connector reads a filtered branch carrying only its own span type, kept separate from the export pipeline so a filter can never drop a span from Distributed Tracing.

There is deliberately no `gen_ai.invoke_workflow.duration`: ADK only opens an `invoke_workflow` span for a `google.adk.workflow.Workflow` node, and this demo is a plain `LlmAgent` with two `AgentTool` sub-agents, so there is no span to derive it from honestly.

### Vertex AI / Gemini Enterprise

This example uses an AI Studio API key so it can run unattended in CI. For Vertex AI, drop `GOOGLE_API_KEY` and add:

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOCATION=<gcp-region>
```

On the managed Agent Engine runtime the container command is not yours to set, so `opentelemetry-instrument` is unavailable; there you need a small bootstrap module imported before `google.adk`, as in the [`google-adk/opentelemetry`](../opentelemetry) example.

> [!TIP]
> For detailed setup instructions and token scopes, see the [AI Observability Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).
