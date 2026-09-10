## GitHub Copilot

This example shows how to enable built-in [OpenTelemetry](https://opentelemetry.io/) telemetry in [GitHub Copilot](https://docs.github.com/en/copilot) and route the data to Dynatrace for full AI Observability, including token usage, model and agent activity, tool calls, and operation latency.

Like the other coding agents in this section, Copilot ships with native OTel support. No code changes are required: you configure telemetry and run Copilot normally.

> [!IMPORTANT]
> **An OpenTelemetry Collector is required for metrics.** The Copilot runtime exports metrics with **cumulative** temporality and provides no setting to change it (`OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` is ignored). Dynatrace [only accepts delta temporality](https://docs.dynatrace.com/docs/ingest-from/opentelemetry/otlp-api#api-limitations) and rejects cumulative metrics with HTTP 400. The included [`collector.yaml`](./collector.yaml) converts them with the `cumulativetodelta` processor.

```
Copilot (CLI / VS Code / SDK)  ──OTLP HTTP:4318──▶  OTel Collector  ──HTTP/protobuf──▶  Dynatrace
                                                    cumulativetodelta
                                                    Api-Token auth
```

The Collector is also what authenticates to Dynatrace. Copilot's telemetry settings expose an endpoint but no per-client headers field, so the token has to live somewhere else.

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

### 1. Run the Collector

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

You need a Dynatrace **classic** access token (`dt0c01.*`) with the `openTelemetryTrace.ingest` and `metrics.ingest` scopes. Platform tokens (`dt0s16.*`) cannot be used for OTLP ingestion. Build the endpoint from your classic domain (no `.apps.`) with the `/api/v2/otlp` base path.

Start the Collector with the included [`collector.yaml`](./collector.yaml):

```bash
make _collector
```

Or run it directly with any Collector distribution that includes `cumulativetodelta`:

```bash
DT_OTEL_ENDPOINT=https://<env-id>.live.dynatrace.com/api/v2/otlp DT_API_TOKEN=dt0c01.<token> otelcol-contrib --config collector.yaml
```

> [!WARNING]
> Port `4318` is a common default and is often already taken, for example by a
> local `dynatrace-otel-collector` or another demo's Collector. A conflicting
> listener **silently swallows** the agent's telemetry: the run succeeds and
> nothing reaches Dynatrace. `make` refuses to start when the port is busy;
> set `OTLP_PORT` to a free port if that happens.

### 2. Point Copilot at the Collector

How you enable telemetry depends on which Copilot surface you use.

#### Copilot CLI and VS Code (enterprise-managed)

For enterprise-managed deployments, telemetry is configured centrally through the `telemetry` property in [enterprise managed settings](https://docs.github.com/en/copilot/reference/enterprise-administrators/enterprise-managed-settings). See [OpenTelemetry for agent monitoring](https://docs.github.com/en/copilot/concepts/enterprise/opentelemetry) and the VS Code guide [Monitor agent usage with OpenTelemetry](https://code.visualstudio.com/docs/agents/guides/monitoring-agents).

Managed settings **do** support a `telemetry.headers` field, so enterprise deployments can authenticate to Dynatrace directly. A Collector is still recommended for the metrics temporality conversion described above.

#### Copilot SDK applications

Applications built on [`@github/copilot-sdk`](https://www.npmjs.com/package/@github/copilot-sdk) pass a `TelemetryConfig` to `CopilotClient`:

```typescript
const client = new CopilotClient({
  gitHubToken: process.env.GH_TOKEN,
  telemetry: {
    otlpEndpoint: "http://localhost:4318",
    otlpProtocol: "http/protobuf",
    captureContent: false,
  },
});
```

`TelemetryConfig` supports `otlpEndpoint`, `otlpProtocol`, `exporterType`, `sourceName`, `filePath`, and `captureContent`. It has **no** headers field, which is why the Collector handles Dynatrace authentication.

That is the entire integration. See [`src/index.ts`](./src/index.ts) for a complete runnable agent.

### 3. Run it

```bash
make install
```

```bash
make run
```

`make run` builds the agent, starts the Collector, and runs one request. Use a custom prompt with:

```bash
npm start -- "What is the current date and time?"
```

## What Copilot Exports

The runtime follows the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) and adds Copilot-specific `github.copilot.*` attributes. Everything below was captured from a live run of this example against a local OTLP receiver.

Telemetry is reported under `service.name = github-copilot`.

### Spans

| Span | Operation |
|---|---|
| `invoke_agent` | Agent invocation, wrapping one turn |
| `chat {model}` | One LLM inference |
| `session.provisioning` / `session.first_turn` | Session lifecycle |

### Span Attributes

| Attribute | Description |
|---|---|
| `gen_ai.provider.name` | Provider identification |
| `gen_ai.operation.name` | `invoke_agent`, `chat` |
| `gen_ai.request.model` | Requested model |
| `gen_ai.response.model` | Model that answered |
| `gen_ai.response.id` | Provider response ID |
| `gen_ai.response.finish_reasons` | e.g. `stop` |
| `gen_ai.usage.input_tokens` | Input token count |
| `gen_ai.usage.output_tokens` | Output token count |
| `gen_ai.conversation.id` | Conversation identifier |
| `gen_ai.agent.id` / `gen_ai.agent.version` | Agent identity |
| `github.copilot.turn_id` / `turn_count` | Turn tracking |
| `github.copilot.token_limit` | Model context limit |

Not emitted by the runtime: `gen_ai.agent.name` (it sends `gen_ai.agent.id` and `gen_ai.agent.version` instead) and `gen_ai.request.temperature`. `gen_ai.token.type` is a dimension on `gen_ai.client.token.usage`, not a span attribute. `span.status_code` is set only on failures.

### Metrics

| Metric | Type | Description |
|---|---|---|
| `gen_ai.client.token.usage` | Histogram | Tokens per operation, split by `gen_ai.token.type` |
| `gen_ai.client.operation.duration` | Histogram | End-to-end operation latency |
| `gen_ai.invoke_agent.duration` | Histogram | Agent invocation duration |
| `gen_ai.invoke_agent.inference_calls` | Histogram | LLM calls per invocation |
| `gen_ai.invoke_agent.tool_calls` | Histogram | Tool calls per invocation |
| `github.copilot.agent.turn.count` | Histogram | Turns per agent session |

`gen_ai.client.token.usage` and `gen_ai.client.operation.duration` are the two metrics the Dynatrace AI Observability app charts directly.

## Content Capture

Prompt, response, tool-argument, and tool-result content is **not exported by default**. Capture is an explicit, privacy-sensitive opt-in: `captureContent` in `TelemetryConfig`, or `COPILOT_CAPTURE_CONTENT=true` for this example.

**If prompts and responses are missing in Dynatrace, this is why.** Three attributes appear only when capture is enabled:

| Attribute | Contains |
|---|---|
| `gen_ai.input.messages` | Prompt messages sent to the model |
| `gen_ai.output.messages` | Model response messages |
| `gen_ai.system_instructions` | System prompt |

The runtime uses these current GenAI convention names, not the legacy indexed `gen_ai.prompt.0.*` / `gen_ai.completion.0.*` form.

Turn it on deliberately and only where appropriate. For a coding agent this content is the developer's source code, along with anything else in the prompt context: credentials, customer data, internal file paths.

## Verify in Dynatrace

1. **AI Observability app**: the agent appears automatically with models, token usage, and traces
2. **Distributed Traces**: search for `service.name = github-copilot`
3. **Metrics browser**: search for `gen_ai.client` and `github.copilot`

You can also verify with DQL in a notebook:

```dql
fetch spans
| filter isNotNull(gen_ai.provider.name)
| filter in(gen_ai.operation.name, {"invoke_agent", "chat", "execute_tool"})
| fields timestamp, span.name, gen_ai.operation.name,
         gen_ai.request.model, gen_ai.usage.input_tokens,
         gen_ai.usage.output_tokens
| limit 50
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DT_ENDPOINT` | (required) | Dynatrace tenant URL; the Makefile appends `/api/v2/otlp` |
| `DT_API_TOKEN` | (required) | Classic Dynatrace token, used by the Collector |
| `GH_TOKEN` | (required) | GitHub token with `Copilot Requests` access, for SDK apps |
| `COPILOT_OTLP_ENDPOINT` | `http://localhost:4318` | Where the runtime sends OTLP |
| `OTLP_PORT` | `4318` | Host port the Collector listens on |
| `COPILOT_CAPTURE_CONTENT` | `false` | Capture prompt, response, and tool content |
| `PROVIDER_MODEL` | `claude-sonnet-4-5-20250929` | Model used by the example |
| `COPILOT_PROVIDER_BASE_URL` | (unset) | BYOK OpenAI-compatible endpoint; used by the e2e suite |
| `COPILOT_PROVIDER_API_KEY` | (unset) | API key for the BYOK endpoint |

## Files

| File | Purpose |
|---|---|
| `src/index.ts` | Example agent with native telemetry enabled |
| `collector.yaml` | Collector config: cumulative-to-delta plus Dynatrace auth |
| `Makefile` | `install`, `build`, `run`, `request`, `stop`, `logs` |
| `.env.example` | Environment variable template |
