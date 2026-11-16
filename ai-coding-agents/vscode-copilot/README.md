# VS Code Copilot Chat - Dynatrace AI Observability

> Native support and configuration verified against Microsoft and Dynatrace primary sources on **2026-09-16**.

VS Code Copilot Chat includes a first-party OpenTelemetry exporter. It can send **traces, metrics, and OTel events** to an OTLP-compatible backend such as Dynatrace. No application-code instrumentation is required.

This editor integration is different from the [`@github/copilot-sdk` example](../github-copilot-sdk/), which manually instruments a custom TypeScript application.

## Native support status

| Signal | Native support | Notes |
|---|---:|---|
| Traces | Yes | Agent invocations, LLM calls, tools, hooks, and errors |
| Metrics | Yes | GenAI duration/token metrics and Copilot-specific activity metrics |
| Logs | Yes, as OTel events | Exported through the OTLP logs pipeline |
| GenAI semantic conventions | Yes | Copilot emits `gen_ai.*` directly; no semconv opt-in is required |

Copilot emits attributes in three namespaces:

- `gen_ai.*` - OpenTelemetry GenAI semantic conventions
- `github.copilot.*` - canonical Copilot-specific attributes
- `copilot_chat.*` - legacy compatibility attributes

Typical traces include `invoke_agent`, `chat`, `execute_tool`, and `execute_hook` operations. Important attributes include:

- `gen_ai.operation.name`
- `gen_ai.provider.name`
- `gen_ai.agent.name`
- `gen_ai.conversation.id`
- `gen_ai.request.model`
- `gen_ai.response.model`
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.tool.name`
- `gen_ai.tool.type`
- `gen_ai.tool.call.id`
- `error.type`

Prompt messages, model responses, tool definitions, tool arguments, tool results, commands, and file paths are not captured by default. Keep content capture disabled unless your organization has explicitly approved it.

## Prerequisites

- A current VS Code release with Copilot Chat OTel support
- Access to GitHub Copilot
- A Dynatrace environment
- A Dynatrace API token with the scopes needed for the signals you export:
  - `openTelemetryTrace.ingest`
  - `metrics.ingest`
  - `logs.ingest`

Never commit the token to source control.

## Configure direct export to Dynatrace from Bash

Dynatrace SaaS uses this OTLP base endpoint:

```text
https://<environment-id>.live.dynatrace.com/api/v2/otlp
```

OTLP/HTTP appends the standard signal paths:

- `/v1/traces`
- `/v1/metrics`
- `/v1/logs`

Dynatrace's OTLP API accepts `http/protobuf`; it does not accept direct OTLP/gRPC or OTLP/JSON. This setup sends telemetry directly from VS Code to Dynatrace, without a local Collector or a workspace `.env` file.

If `code` is not found on macOS, open the Command Palette in VS Code and run **Shell Command: Install 'code' command in PATH**, then open a new terminal.

Fully quit all VS Code instances before launching from this shell so the running app receives the environment variables. Replace the endpoint's environment ID, then paste this block into Bash:

```bash
export DYNATRACE_API_TOKEN="token"
export OTEL_EXPORTER_OTLP_ENDPOINT="https://<environment-id>.live.dynatrace.com/api/v2/otlp"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Api-Token ${DYNATRACE_API_TOKEN}"
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE="delta"
export COPILOT_OTEL_ENABLED="true"
export COPILOT_OTEL_CAPTURE_CONTENT="false"
export OTEL_SERVICE_NAME="copilot-chat"
export OTEL_RESOURCE_ATTRIBUTES="service.namespace=developer-tools,deployment.environment.name=development"

code .
```

The token is read without terminal echo or being typed into the shell command, but it is still present in the exported OTLP header and available to the VS Code process and its extensions. This avoids storing it in a workspace file or VS Code settings, but it is not as isolated as using a Collector to hold the credential. `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta` is important for Dynatrace metric ingestion.

> [!IMPORTANT]
> Do not put a real token in checked-in files, VS Code workspace settings, shell scripts, or JSON examples. Keep `.env` files closed and do not attach or select them in chat; workspace exclusions reduce accidental discovery but do not prevent explicit attachment.

## Optional user settings

The included [`settings.example.json`](./settings.example.json) is an optional VS Code user-settings fragment. Merge its top-level properties into your User `settings.json` (or set the same options in the Settings UI); it is not a `managed-settings.json` file. The Bash launch above configures the exporter endpoint, authentication header, and metric temporality without putting a token in `settings.json`.

Current user-facing keys are under `github.copilot.chat.otel.*`. Internal enterprise-policy mappings may use `chat.agentHost.otel.*`; do not paste those internal keys into normal user settings.

Environment variables take precedence over user settings. Managed telemetry overrides user settings, but environment variables can still override managed values in the Copilot Chat extension. To ensure managed telemetry takes effect, admins should remove conflicting OTel environment variables.

## Enterprise-managed configuration

Admins can centrally govern the exporter through the `telemetry` block in Copilot managed settings. Delivery options include native MDM, server-managed GitHub organization/enterprise settings, and file-based `managed-settings.json`.

```json
{
  "telemetry": {
    "enabled": true,
    "endpoint": "https://<environment-id>.live.dynatrace.com/api/v2/otlp",
    "protocol": "http/protobuf",
    "captureContent": false,
    "serviceName": "copilot-chat",
    "resourceAttributes": {
      "service.namespace": "developer-tools",
      "deployment.environment.name": "development"
    },
    "headers": {
      "Authorization": "Api-Token <inject-with-approved-secret-management>"
    }
  }
}
```

Managed values override corresponding environment and user values. Reload VS Code after a managed telemetry value changes because the agent host resolves its configuration when it starts.

Managed `telemetry.headers` are not propagated through environment variables into tool subprocesses. This protects the token from commands spawned by the agent, but separately launched Copilot CLI sessions need their own approved export route or a local collector/gateway.

## Content-capture policy

Content capture is disabled in every example here:

```text
COPILOT_OTEL_CAPTURE_CONTENT=false
```

Enabling it can export prompts, responses, source code, system instructions, tool schemas, tool arguments, tool results, commands, and file paths. Obtain explicit privacy and security approval before changing it.

## Dynatrace AI Observability compatibility

| AI Observability concern | Copilot output | Status |
|---|---|---|
| Operation detection | `gen_ai.operation.name` | Good |
| Provider | `gen_ai.provider.name` | Good |
| Requested/resolved model | `gen_ai.request.model`, `gen_ai.response.model` | Good |
| Token usage | `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | Good |
| Agent identity | `gen_ai.agent.name` | Good |
| Conversation correlation | `gen_ai.conversation.id` | Good |
| Tool visibility | `gen_ai.tool.*`, `github.copilot.*` | Good; custom fields may not be first-class app dimensions |
| Errors | Span status and `error.type` | Good |
| Prompt/completion bodies | Content-capture fields | Deliberately absent by default |
| Monetary cost | No documented native cost attribute | Gap; requires external pricing/enrichment |

### Known gaps and caveats

1. Content is absent by default. This is intentional and recommended.
2. Copilot does not document a native monetary-cost attribute; calculate cost separately if needed.
3. `github.copilot.*` fields remain queryable, but not every custom field is guaranteed to be promoted in an AI Observability app view.
4. Older custom examples and dashboards may depend on `llm.request.type="chat"`. Native VS Code export follows the current `gen_ai.*` conventions instead.
5. Terminal Copilot CLI sessions can appear as independent root traces under service `github-copilot`.
6. Managed authentication headers are not forwarded to those separate terminal processes.
7. If you configure a signal-specific traces endpoint rather than the generic base endpoint, include the full `/v1/traces` path and validate delivery.

## Validate the integration

1. Keep content capture disabled.
2. Reload VS Code after configuration changes.
3. Run a benign Copilot agent task that performs at least one model call and one tool call.
4. Confirm OTLP/HTTP requests arrive at the trace, metric, and log ingest paths.
5. Query raw spans in Dynatrace by `service.name == "copilot-chat"`.
6. Verify a `chat` span has provider, model, operation, and token attributes.
7. Verify an `invoke_agent` span has `gen_ai.agent.name` and `gen_ai.conversation.id`.
8. Verify an `execute_tool` span has the relevant `gen_ai.tool.*` fields.
9. Confirm sensitive content attributes are absent.
10. Confirm model calls and agent topology appear in the Dynatrace AI Observability app.
11. Validate metrics independently; successful traces do not prove successful metrics.

If telemetry is missing, inspect the Copilot Chat OTel logs, verify `http/protobuf`, check the base URL, confirm the token scopes, and make sure VS Code was launched with the intended environment.

## Version note

This example intentionally does not pin the Copilot Chat extension. Use a current supported VS Code/Copilot release and re-check Microsoft's linked documentation when upgrading.

The separate `github-copilot-sdk` sample currently pins `@github/copilot-sdk` `1.0.13`; `1.0.14` was the latest release found on 2026-09-16. That unrelated dependency was not changed here because it should be built and tested in a separate update.

## Sources

Checked 2026-09-16:

- [Microsoft: Monitor agent usage with OpenTelemetry](https://code.visualstudio.com/docs/agents/guides/monitoring-agents)
- [Microsoft: Manage AI settings in enterprise environments](https://code.visualstudio.com/docs/enterprise/ai-settings#_configure-telemetry-export-with-opentelemetry)
- [VS Code Copilot Chat OTel source](https://github.com/microsoft/vscode-copilot-chat/tree/main/src/platform/otel)
- [Dynatrace OTLP API endpoints](https://docs.dynatrace.com/docs/ingest-from/opentelemetry/otlp-api)
- [Dynatrace: OpenTelemetry and AI Observability](https://docs.dynatrace.com/docs/observe/dynatrace-for-ai-observability/get-started/opentelemetry)
- [Dynatrace AI Observability app](https://docs.dynatrace.com/docs/observe/dynatrace-for-ai-observability/ai-observability-app)
- [VS Code issue #335163: signal-specific traces endpoint path](https://github.com/microsoft/vscode/issues/335163)
- [`@github/copilot-sdk` releases](https://github.com/github/copilot-sdk/releases)
