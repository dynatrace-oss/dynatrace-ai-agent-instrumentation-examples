## Claude Code

This example shows how to enable built-in [OpenTelemetry](https://opentelemetry.io/) telemetry in [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and route the data to Dynatrace for full AI Observability — including token usage, costs, engineering metrics, session activity, and tool events.

Unlike SDK-based frameworks, Claude Code ships with native OTEL support. No code changes are required: you only need to set a handful of environment variables before running `claude`.

![Claude Code Dynatrace Dashboard](./dashboard-claude-code-monitoring.png)

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

Claude Code has [built-in OpenTelemetry support](https://code.claude.com/docs/en/monitoring-usage). Enabling it is a matter of exporting the right environment variables before starting `claude`.

Set the variables below (or `source setup.sh` — see [How to use](#how-to-use)):

```bash
# 1. Enable telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# 2. Choose OTLP exporters (Dynatrace ingests metrics and logs)
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp

# 3. Use HTTP/protobuf — the protocol Dynatrace expects
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# 4. Point to your Dynatrace OTLP ingest endpoint (base URL, no signal suffix)
#    SaaS production:  https://<env-id>.live.dynatrace.com/api/v2/otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=https://<YOUR_ENV_ID>.live.dynatrace.com/api/v2/otlp

# 5. Authenticate with a Dynatrace API token (openTelemetryTrace.ingest scope)
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token <YOUR_DT_TOKEN>"

# 6. Dynatrace requires delta temporality for metrics
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta

# 7. Traces (beta) — REQUIRED for the AI Observability app.
#    Metrics and logs alone do not appear there; the app is span-driven.
export CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1
export OTEL_TRACES_EXPORTER=otlp
```

Once set, start Claude Code normally:

```bash
claude
```

Every session will now export the following data to Dynatrace:

### Metrics

| Metric | Description |
|---|---|
| `claude_code.session.count` | Sessions started |
| `claude_code.token.usage` | Tokens consumed (`input`, `output`, `cacheRead`, `cacheCreation`) per model |
| `claude_code.cost.usage` | Estimated USD cost per model |
| `claude_code.lines_of_code.count` | Lines added / removed |
| `claude_code.commit.count` | Git commits created by Claude Code |
| `claude_code.pull_request.count` | Pull requests created by Claude Code |
| `claude_code.code_edit_tool.decision` | Accept / reject decisions per tool |
| `claude_code.active_time.total` | Active time (`user` input vs. `cli` processing) |

### Log events

| Event | Description |
|---|---|
| `claude_code.user_prompt` | Submitted prompts (content redacted by default) |
| `claude_code.api_request` | Per-request token counts, costs, latency, and model |
| `claude_code.api_error` | API failures with status codes and error messages |
| `claude_code.tool_result` | Tool executions with success/failure, duration, and decision |
| `claude_code.tool_decision` | Accept / reject decisions per tool |

All signals carry common attributes (`session.id`, `user.id`, `user.email`, `organization.id`, `app.version`, `terminal.type`) that let you slice data by user, team, or session.

## How to use

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed (`npm install -g @anthropic-ai/claude-code`)
- A Dynatrace environment with an API token that has the **`openTelemetryTrace.ingest`** scope

### Configure Dynatrace credentials

Copy the example env file and fill in your values:

```bash
cp .env.example .env
# edit .env with your DT_API_TOKEN and DT_OTEL_ENDPOINT
```

The `.env` file uses two variables:

| Variable | Description |
|---|---|
| `DT_API_TOKEN` | Dynatrace API token with `openTelemetryTrace.ingest` scope |
| `DT_OTEL_ENDPOINT` | Base OTLP endpoint — **do not** include `/v1/traces` or other signal suffixes |

Endpoint format by environment type:

| Environment | Endpoint format |
|---|---|
| SaaS production | `https://<env-id>.live.dynatrace.com/api/v2/otlp` |

### Enable telemetry and run Claude Code

#### Option 1: Managed settings file (recommended)

For persistent local setup, use Claude Code's [managed settings file](https://code.claude.com/docs/en/settings#settings-files). This is the recommended approach because settings persist across terminal sessions and apply automatically when you run `claude`.

Create or edit `~/.config/claude-code/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "https://<YOUR_ENV_ID>.live.dynatrace.com/api/v2/otlp",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Api-Token <YOUR_DT_TOKEN>",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "delta"
  }
}
```

Replace `<YOUR_ENV_ID>` and `<YOUR_DT_TOKEN>` with your Dynatrace environment ID and API token.

Then simply run:

```bash
claude
```

#### Option 2: Source the setup script

Alternatively, source the setup script to export environment variables into your current shell:

```bash
source setup.sh
claude
```

> [!NOTE]
> The setup script must be **sourced** (not executed) so that the exported variables are available in your current shell session. You'll need to source the script each time you open a new terminal.

### Test the connection

Before running a full session you can verify end-to-end connectivity by running the test script. It sends a representative set of metrics and log events to Dynatrace and reports the result:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 test_connection.py
```

A successful run looks like:

```
Sending test telemetry to: https://<env-id>.live.dynatrace.com/api/v2/otlp
────────────────────────────────────────────────────────────
Recording test metrics …
Recording test log events …

Flushing … (waiting 7 s for the metric export interval)
✓  Metrics exported successfully
✓  Log events exported successfully

────────────────────────────────────────────────────────────
Done! Open your Dynatrace tenant and look for:
  Metrics : Metrics browser → search 'claude_code'
  Logs    : Log & Event Viewer → filter by service.name = claude-code
```

### Verify in Dynatrace

After running Claude Code (or the test script), open your Dynatrace tenant and import the attached dashboard, or run this DQL query in a notebook to fetch logs:

```dql
fetch logs, from:now()-1h
| filter service.name == "claude-code"
| limit 50
```

- **Metrics browser** – search for `claude_code` to see all emitted metrics
- **Log & Event Viewer** – filter by `service.name = claude-code` to see session events
- **AI Observability app** – requires trace export (beta) and, for the full experience, the GenAI semconv enrichment (OpenPipeline at ingest, or the Collector variant in transit); see [Light up the AI Observability app](#light-up-the-ai-observability-app)

## Light up the AI Observability app

> [!IMPORTANT]
> The Dynatrace **AI Observability** app (`dynatrace.genai.observability`) is **span-driven**: its Explorer, Prompts, and Agents topology views are computed from spans that follow the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/). With only metrics and logs configured (steps 1–6 above), the app stays **empty** — the data is still there, but only in the Metrics browser, Logs, and the bundled dashboard.

Two steps get Claude Code sessions into the app:

### Step 1 — Enable trace export (beta)

Claude Code can export spans linking each user prompt to the API requests and tool executions it triggers ([docs](https://code.claude.com/docs/en/monitoring-usage)). Add to your environment (or managed settings `env` block):

```bash
export CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1
export OTEL_TRACES_EXPORTER=otlp
```

The token needs the `openTelemetryTrace.ingest` scope (already required above). After the next session, the app's **Overview** and **Explorer** show your `claude-code` AI app, models, and LLM request counts, and each interaction is a full distributed trace (`claude_code.interaction` → `claude_code.llm_request` / `claude_code.tool`).

### Step 2 — Map Claude Code spans to GenAI semantic conventions

Claude Code's spans carry only a subset of the GenAI conventions (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.id`). The app's token/cost tiles, Prompts stream, and Agents topology read attributes Claude Code does not emit — `gen_ai.operation.name`, `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`, `gen_ai.agent.name` / `gen_ai.agent.id`, `gen_ai.input.messages`. The [`openpipeline/`](./openpipeline/) folder contains a span-processing pipeline that derives them at ingest from the attributes Claude Code *does* send:

| Claude Code span | Mapped to | Added attributes |
|---|---|---|
| `claude_code.llm_request` | `chat` | `gen_ai.operation.name`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.model`, `gen_ai.provider.name` |
| `claude_code.interaction` | `invoke_agent` | `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.input.messages` (from `user_prompt`, requires `OTEL_LOG_USER_PROMPTS=1`) |
| `claude_code.tool` | `execute_tool` | `gen_ai.tool.name` |

Apply it with the [dtctl CLI](https://github.com/dynatrace-oss/dtctl) (or recreate it manually in the OpenPipeline app) — see [`openpipeline/README.md`](./openpipeline/README.md) for the two commands. With the pipeline in place, token usage appears per app/model in the Explorer, and interactions surface with their prompt text.

Prefer the enrichment in transit instead of at ingest? [`collector/`](./collector/) contains the identical mappings as an OpenTelemetry Collector `transform` processor (OTTL) — route Claude Code through the collector and the resulting spans are the same. [`collector/README.md`](./collector/README.md) compares the two placements; use one or the other.

### Verify

```dql
fetch spans, from:now()-1h
| filter service.name == "claude-code"
| fields start_time, span.name, gen_ai.operation.name, gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, gen_ai.tool.name
| sort start_time desc
```

Spans should show `dt.openpipeline.pipelines` = the custom pipeline, and `gen_ai.operation.name` filled. Then open **AI Observability → Explorer**.

### Optional configuration

| Variable | Default | Description |
|---|---|---|
| `OTEL_METRIC_EXPORT_INTERVAL` | `60000` | Metric flush interval in ms. Use `10000` during debugging. |
| `OTEL_LOGS_EXPORT_INTERVAL` | `5000` | Log flush interval in ms. |
| `OTEL_LOG_USER_PROMPTS` | disabled | Set to `1` to include prompt content in log events. |
| `OTEL_LOG_TOOL_DETAILS` | disabled | Set to `1` to include MCP server/tool names in tool events. |
| `OTEL_RESOURCE_ATTRIBUTES` | — | Add custom attributes, e.g. `department=engineering,team.id=platform`. |
| `OTEL_METRICS_INCLUDE_SESSION_ID` | `true` | Include `session.id` in metrics (affects cardinality). |
| `OTEL_METRICS_INCLUDE_ACCOUNT_UUID` | `true` | Include `user.account_uuid` in metrics. |

### Administrator / centralized configuration

For organization-wide deployment, configure telemetry via the [managed settings file](https://code.claude.com/docs/en/settings#settings-files) (distributable via MDM):

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "https://<YOUR_ENV_ID>.live.dynatrace.com/api/v2/otlp",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Api-Token <YOUR_DT_TOKEN>",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "delta"
  }
}
```
