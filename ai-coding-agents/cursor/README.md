# Cursor Enterprise OpenTelemetry export to Dynatrace

This example sends Cursor's native Enterprise OpenTelemetry export to Dynatrace and analyzes the available GenAI-adjacent telemetry with a premade dashboard.

> **Verified 2026-09-25:** Cursor's server-side exporter sends **metrics and logs only** over OTLP/HTTP protobuf. It does **not send traces**, trace/span IDs, or native `gen_ai.*` semantic-convention spans. This example is deliberately log/metric-driven and does not populate the span-based Dynatrace AI Observability topology or trace views.

## Included

- `cursor-monitoring-dashboard.json`: dashboard for requests, tokens, cost, errors, latency, conversations, tools, skills, hooks, users, surfaces, and optional content.
- `k8s/cursor-real-test.yaml`: a Kubernetes Job that installs and runs the real Cursor headless CLI against an embedded, deliberately broken Node.js repository.
- `docker/Dockerfile`, `docker/docker-compose.yml`: Docker files to build a self-contained test image and run it locally with docker compose.
- `cursor-test_connection.py` (or `test_connection.py` in older bundles): optional synthetic Cursor-shaped OTLP emitter for connectivity diagnostics only. It is not used by the real test and does not instrument Cursor.
- `cursor-test_dashboard.py` (or `test_dashboard.py`): dashboard contract checks.
- `.env.example`, `cursor-requirements.txt`, and `Makefile`: test setup and automation.

## Native export surface

Cursor administrators configure export in **Team Settings &gt; OpenTelemetry Export**. It is server-side; there is no Cursor SDK, local editor extension, or instrumentation package to update.

Metrics (delta temporality):

- `cursor.token.usage`, by `cursor.token.type`
- `cursor.tool.calls`, including built-in and MCP tools
- `cursor.cost.usage`, a best-effort estimate rather than an invoice

Logs include `cursor.api.request`, `cursor.api.error`, `cursor.api.correction`, skills, hooks, plugins, Cloud Agent lifecycle events, Grok Bot actions, and opt-in `cursor.conversation.*` messages.

Logs are delivered at least once, so deduplicate on `cursor.event.id` for exact views. Metrics are delivered at most once and contain no request/conversation IDs. Use logs for session-level joins.

## Privacy

Conversation content is off by default. Enable it only after explicit privacy and security approval. It currently covers Cloud Agents and Grok Bot, not IDE/CLI/desktop conversations. The dashboard's message tile stays empty when content export is disabled.

## Prerequisites

- A Cursor account with a user API key stored as `CURSOR_API_KEY`
- Cursor Enterprise and team telemetry administration permission for native OTel export
- (For Kubernetes flow) a working Kubernetes context and `kubectl`
- Dynatrace environment
- Dynatrace API token with log and metric ingest permissions, configured in Cursor Team Settings
- Publicly reachable HTTPS OTLP/HTTP protobuf endpoint

The hosted `gpt-4o-mini` test does not require an OpenAI API key. Never commit Cursor or Dynatrace tokens.

## Configure Cursor

Important — enable server-side collection before running the example

This example relies on Cursor's server-side OpenTelemetry export. Creating activity with the Cursor CLI (the container/job) is necessary but not sufficient: Cursor must be configured to export logs and metrics from the team that owns the `CURSOR_API_KEY`.

In **Team Settings &gt; OpenTelemetry Export**:

1. Create a destination.
2. Use this base URL (no signal suffix):
  ```text
   https://<environment-id>.live.dynatrace.com/api/v2/otlp
  ```
3. Add the HTTP header (replace with your token):
  ```text
   Authorization: Api-Token <YOUR_DYNATRACE_API_TOKEN>
  ```
4. Test the connection and confirm it succeeds.
5. IMPORTANT — enable the telemetry families you want to receive in Dynatrace. At minimum enable:
- Logs (required for request-level and conversation events)
- Metrics (required for token and cost metrics)


Optionally enable others as needed:
- `hooks`, `skills`, `plugins` — for skill and hook events
- `conversation_content` — for opt-in message content (enable only after privacy approval)
- `actions` / `grok_bot_agent_actions` — enable Action Recording if you expect Grok Bot actions (enable Action Recording first)
6. Save and enable the destination. The UI will show whether the destination is active.

Cursor appends `/v1/metrics` and `/v1/logs`. OTLP/gRPC and OTLP/JSON are not supported for the native export.

Verification tips

- Use the destination "Test connection" button — it should report success.
- After running the real test container, wait a few minutes and query Dynatrace for logs and metrics (see Import and test). If no telemetry appears, re-check that the destination is enabled and that the families above are toggled ON for that destination.

Security reminder: only enable `conversation_content` after explicit privacy and security approval; it is off by default.

## Import and test

Import `cursor-monitoring-dashboard.json` in Dynatrace Dashboards or apply it with your normal `dtctl` workflow.

To send representative synthetic data or run the real emitter locally, prepare environment variables first:

```bash
cp .env.example .env
# Edit .env; never commit it.
```

Option A — Run the emitter directly (no Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r cursor-requirements.txt
python3 cursor-test_connection.py --emit-real
```

Option B — Run with Docker Compose (self-contained, recommended)

This repository includes a Dockerfile and docker-compose.yml placed under `docker/`. The image bundles the repo and pinned dependencies so you don't need Python or pip on the host.

```bash
# Build and run using docker compose (recommended)
cp .env.example .env
# Edit .env to set CURSOR_API_KEY (and optional DT_* vars)

docker compose -f docker/docker-compose.yml up --build

# When finished, tear down the containers:
docker compose -f docker/docker-compose.yml down
```

You can also use the Makefile convenience targets if present:

```bash
make preflight         # run the local preflight check
make docker-build      # build the test image
make compose-up        # docker compose -f docker/docker-compose.yml up --build
make compose-down      # docker compose -f docker/docker-compose.yml down
```

The Job creates genuine Cursor activity, but **native OTel delivery remains server-side**. `CURSOR_API_KEY` authenticates the CLI; it does not configure telemetry export. The Cursor organization administrator must separately enable the required log and metric families in **Team Settings &gt; OpenTelemetry Export**. A successful Job proves the real Cursor workload ran; the dashboard proves export and ingestion worked.

The test should populate API-request, model, token, tool-call, cost, latency, user, surface, and conversation-related views when those export families are enabled. Error, skill, hook, plugin, and conversation-content tiles can legitimately remain empty because the successful test does not deliberately create errors or enable privacy-sensitive content capture.

The synthetic emitter remains available only as an isolated transport diagnostic:

```bash
# local python-based emitter (diagnostic only)
make setup
make emit
```

Verify real Cursor logs:

```dql
fetch logs, from: now()-2h
| filter `service.name` == "cursor"
| filter startsWith(`event.name`, "cursor.")
| fields timestamp, `event.name`, cursor.conversation.id, cursor.model.name
| sort timestamp desc
```

Verify real Cursor metrics:

```dql
timeseries tokens = sum(`cursor.token.usage`), by: {cursor.token.type}, from: now()-2h
```

## GenAI-style insights available from logs


| Question                         | Cursor source                                     |
| -------------------------------- | ------------------------------------------------- |
| Models used                      | `cursor.model.name`                               |
| Input/output/cache tokens        | Request token attributes and `cursor.token.usage` |
| Busiest sessions                 | Group request logs by `cursor.conversation.id`    |
| Users and surfaces               | `cursor.user.id`, `cursor.surface`                |
| Failures                         | `cursor.api.error`                                |
| Request latency                  | `cursor.api.request.duration_ms`                  |
| Skills/hooks/plugins             | Dedicated event families                          |
| Approved prompt/response content | Opt-in `cursor.conversation.*` logs               |

