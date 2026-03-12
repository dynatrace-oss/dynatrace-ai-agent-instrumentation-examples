## OpenClaw

This example shows how to enable the built-in [OpenTelemetry](https://opentelemetry.io/) diagnostics plugin in [OpenClaw](https://openclaw.ai/) and route the data to Dynatrace for full AI Observability — including token usage, costs, model latency, session activity, and tool events.

OpenClaw ships with a `diagnostics-otel` plugin that exports traces, metrics, and logs over OTLP/HTTP. No additional code is required: you only need to configure `openclaw.json` and set a few environment variables before starting the gateway.

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

OpenClaw has a [built-in diagnostics-otel plugin](https://docs.openclaw.ai/logging) that exports OpenTelemetry signals. Enable it using the `openclaw config` CLI:

```bash
openclaw config set diagnostics.enabled true
openclaw config set diagnostics.otel.enabled true
openclaw config set diagnostics.otel.traces true
openclaw config set diagnostics.otel.metrics true
openclaw config set diagnostics.otel.logs true
openclaw config set diagnostics.otel.protocol http/protobuf
openclaw config set diagnostics.otel.endpoint "https://<TENANT>.live.dynatrace.com/api/v2/otlp"
openclaw config set diagnostics.otel.headers '{"Authorization":"Api-Token dt0c01.B6WWXZZZZZ.XXXZZZXXX..."}'
openclaw config set diagnostics.otel.serviceName "openclaw-gateway"
```

Replace `<TENANT>` with your Dynatrace environment ID and the `Api-Token` value with your actual Dynatrace API token (requires the **`openTelemetryTrace.ingest`**, **`metrics.ingest`**, **`logs.ingest`** scopes).

Once configured, start OpenClaw normally:

```bash
openclaw start
```

Every session will now export the following data to Dynatrace:

### Metrics

| Metric                         | Description                                                |
| ------------------------------ | ---------------------------------------------------------- |
| `openclaw.tokens`              | Token usage by type (`input`, `output`, `cache`) per model |
| `openclaw.cost.usd`            | Estimated USD cost per model                               |
| `openclaw.run.duration_ms`     | Agent run duration in milliseconds                         |
| `openclaw.context.tokens`      | Context window usage                                       |
| `openclaw.webhook.received`    | Webhooks received                                          |
| `openclaw.webhook.duration_ms` | Webhook processing duration                                |
| `openclaw.message.queued`      | Messages queued for processing                             |
| `openclaw.message.processed`   | Messages processed                                         |
| `openclaw.message.duration_ms` | Message processing duration                                |
| `openclaw.queue.depth`         | Current queue depth                                        |
| `openclaw.session.state`       | Session state transitions                                  |
| `openclaw.run.attempt`         | Run attempts                                               |

### Trace spans

| Span                         | Description                                 |
| ---------------------------- | ------------------------------------------- |
| `openclaw.model.usage`       | Model invocation with token counts and cost |
| `openclaw.webhook.processed` | Webhook processing lifecycle                |
| `openclaw.webhook.error`     | Webhook errors                              |
| `openclaw.message.processed` | Message processing lifecycle                |
| `openclaw.session.stuck`     | Stuck session detection                     |

### Log events

| Event                  | Description                                                                   |
| ---------------------- | ----------------------------------------------------------------------------- |
| Structured log records | Same records written to the gateway log file, exported over OTLP when enabled |

## How to use

### Prerequisites

- [OpenClaw](https://openclaw.ai/) installed and configured
- A Dynatrace environment with an API token that has the **`openTelemetryTrace.ingest`**, **`metrics.ingest`**, **`logs.ingest`** scopes

### Configure the `.env` file

Copy the example env file:

```bash
cp .env.example .env
```

The `.env` file contains:

| Variable                                            | Description                                                                   |
| --------------------------------------------------- | ----------------------------------------------------------------------------- |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | **Must** be set to `delta` — Dynatrace requires delta temporality for metrics |

### Enable telemetry and run OpenClaw

#### Option 1: OpenClaw CLI configuration (recommended)

Configure the `diagnostics-otel` plugin using the `openclaw config` CLI as shown in the [Dynatrace Instrumentation](#dynatrace-instrumentation) section above. Settings are persisted in `~/.openclaw/openclaw.json` and apply automatically on every start.

Then simply run:

```bash
openclaw start
```

#### Option 2: Run the setup script

Alternatively, run the setup script with your Dynatrace endpoint and API token. It calls `openclaw config set` for each setting and writes `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` to `~/.openclaw/.env`:

```bash
./setup.sh https://<env-id>.live.dynatrace.com/api/v2/otlp <YOUR_DT_TOKEN>
openclaw start
```

> [!NOTE]
> The setup script only needs to be run once. Settings are persisted in `~/.openclaw/openclaw.json` and `~/.openclaw/.env`.

### Test the connection

Before running a full session you can verify end-to-end connectivity by running the test script. It sends a representative set of metrics, traces, and log events to Dynatrace and reports the result:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 test_connection.py https://<env-id>.live.dynatrace.com/api/v2/otlp <YOUR_DT_TOKEN>
```

A successful run looks like:

```
Sending test telemetry to: https://<env-id>.live.dynatrace.com/api/v2/otlp
────────────────────────────────────────────────────────────
Recording test metrics …
Recording test trace spans …
Recording test log events …

Flushing … (waiting 7 s for the export interval)
✓  Metrics exported successfully
✓  Traces exported successfully
✓  Log events exported successfully

────────────────────────────────────────────────────────────
Done! Open your Dynatrace tenant and look for:
  Metrics : Metrics browser → search 'openclaw'
  Traces  : Distributed traces → filter by service.name = openclaw-gateway
  Logs    : Log & Event Viewer → filter by service.name = openclaw-gateway
```

### Verify in Dynatrace

After running OpenClaw (or the test script), open your Dynatrace tenant and import the attached dashboard, or run this DQL query in a notebook to fetch logs:

```dql
fetch logs, from:now()-1h
| filter service.name == "openclaw-gateway"
| limit 50
```

- **Metrics browser** – search for `openclaw` to see all emitted metrics
- **Distributed traces** – filter by `service.name = openclaw-gateway` to see trace spans
- **Log & Event Viewer** – filter by `service.name = openclaw-gateway` to see structured log events

### Optional configuration

| Setting (openclaw.json)                             | Default      | Description                                                      |
| --------------------------------------------------- | ------------ | ---------------------------------------------------------------- |
| `diagnostics.otel.sampleRate`                       | `1.0`        | Trace sampling rate (0.0–1.0, root spans only)                   |
| `diagnostics.otel.flushIntervalMs`                  | `60000`      | Metric/trace flush interval in ms. Use `10000` during debugging. |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | `cumulative` | Set to `delta` for Dynatrace compatibility                       |
