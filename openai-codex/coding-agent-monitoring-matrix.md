# Coding Agent Monitoring Matrix (OTEL Focus)

_As of March 5, 2026._

| Tool | Type | Native OTEL/OTLP export | What you get | Setup effort |
|---|---|---|---|---|
| **OpenAI Codex CLI** | Terminal agent | **Yes** | OTEL logs/events + metrics via `[otel]` config (`otlp-http`/`otlp-grpc`) | **Easy** |
| **Claude Code** | Terminal agent | **Yes (beta)** | OTEL metrics + logs/events via env vars (`OTEL_*`) | **Easy** |
| **Gemini CLI** | Terminal agent | **Yes** | OTEL-based observability (logs + metrics), OTLP endpoint/protocol config | **Easy-Med** |
| **Cline** | IDE agent (VS Code) | **Yes** | OTLP metrics + logs (no distributed tracing yet) | **Med** |
| **GitHub Copilot coding agent** | GitHub/IDE/CLI surfaces | **No native OTEL docs** | Session logs, agents page, usage metrics dashboard + APIs | **Easy (non-OTEL)** |
| **Cursor Agent / Cursor CLI** | IDE + terminal + background agents | **No native OTEL docs found** | Admin/analytics APIs, AI code tracking API, agent/session APIs | **Med (API integration)** |
| **Windsurf (Cascade/Editor/Plugins)** | IDE/agent | **No native OTEL docs found** | Built-in analytics + Enterprise Analytics API | **Med (API integration)** |
| **Amazon Q Developer** | IDE/cloud assistant | **No native OTEL docs** | CloudWatch metrics, CloudTrail logs, activity dashboards, prompt logs | **Med** |
| **Devin** | Cloud autonomous coding agent | **No native OTEL docs found** | Org/enterprise audit log APIs | **Med** |
| **Replit Agent** | Cloud/IDE agent | **No native OTEL docs found** | Console/run logs, Enterprise audit logs + SIEM streaming | **Med** |
| **Junie CLI (JetBrains)** | Terminal/IDE agent | **No native OTEL docs found** | ACP logs, request logging options, org AI activity analytics | **Med** |
| **Roo Code** | IDE + cloud agents | **No native OTEL docs found** | Product telemetry (PostHog-based), privacy/telemetry controls | **Easy (non-OTEL)** |
| **Aider** | Terminal coding agent | **No OTEL (public docs)** | Anonymous analytics opt-in/out | **Easy (limited)** |
| **Continue** | IDE extension/agentic workflows | **No OTEL (public docs)** | Anonymous telemetry (PostHog), opt-out controls | **Easy (limited)** |

## OTEL-First Shortlist

If your requirement is easy, first-party OTEL export, the strongest options are:

1. OpenAI Codex CLI
2. Claude Code
3. Gemini CLI
4. Cline (OTLP metrics/logs, but no distributed tracing yet)

## Sources

- <https://developers.openai.com/codex/security/>
- <https://docs.claude.com/en/docs/claude-code/monitoring-usage>
- <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/telemetry.md>
- <https://docs.cline.bot/enterprise-solutions/monitoring/opentelemetry>
- <https://docs.cline.bot/enterprise-solutions/monitoring/overview>
- <https://docs.github.com/copilot/how-tos/agents/copilot-coding-agent/tracking-copilots-sessions>
- <https://docs.github.com/copilot/how-tos/agents/copilot-coding-agent/using-the-copilot-coding-agent-logs>
- <https://docs.github.com/copilot/concepts/copilot-metrics>
- <https://docs.cursor.com/en/cli/overview>
- <https://docs.cursor.com/account/teams/admin-api>
- <https://docs.cursor.com/en/account/teams/ai-code-tracking-api>
- <https://docs.windsurf.com/windsurf/guide-for-admins>
- <https://docs.windsurf.com/windsurf/accounts/api-reference/introduction>
- <https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/monitoring-overview.html>
- <https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/monitoring-cloudwatch.html>
- <https://docs.devin.ai/enterprise/api-reference/audit-logs>
- <https://docs.replit.com/teams/identity-and-access-management/audit-logs>
- <https://docs.replit.com/replit-workspace/workspace-features/console-shell>
- <https://junie.jetbrains.com/docs/junie-cli.html>
- <https://www.jetbrains.com/help/ai-assistant/acp.html>
- <https://www.jetbrains.com/help/ai/data-retention.html>
- <https://github.com/RooCodeInc/Roo-Code/blob/main/PRIVACY.md>
- <https://roocode.com/privacy>
- <https://aider.chat/docs/more/analytics.html>
- <https://docs.continue.dev/telemetry/>
