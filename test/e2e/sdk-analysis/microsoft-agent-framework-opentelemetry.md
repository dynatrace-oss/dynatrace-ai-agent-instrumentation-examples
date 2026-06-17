# Microsoft Agent Framework — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.2.0 | **Path**: `microsoft-agent-framework/opentelemetry/app.py` | **Profile**: azure | **Dashboard**: `azureai.dashboard.json` | **Branch**: `microsoft`

## Instrumentation

- **Library**: `agent-framework` + `agent-framework-openai` (Dynatrace custom framework); `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http`
- **Provider**: Azure OpenAI (`OpenAIChatCompletionClient` with `azure_endpoint`)
- **OTel setup**: Custom `_configure_dynatrace_otlp()` sets both trace and metrics OTLP endpoints directly to Dynatrace (`DT_ENDPOINT`). Delta temporality configured via `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`. `configure_otel_providers(enable_sensitive_data=True)` initialises both `TracerProvider` and `MeterProvider`.
- **Agent**: `Agent.run()` routes through `AgentTelemetryLayer` (sets `gen_ai.agent.name`). Direct `client.get_response()` would only hit `ChatTelemetryLayer` and would not emit `gen_ai.agent.name`.
- **Content capture**: `enable_sensitive_data=True` enables `gen_ai.input.messages` / `gen_ai.output.messages`.
- **Temperature & conversation**: `temperature` and `conversation_id` (UUID) passed via `default_options` — framework likely maps these to `gen_ai.request.temperature` (AR-042) and `gen_ai.conversation.id` (AR-041).
- **Provider flush**: Explicit `force_flush()` + `shutdown()` on both trace and metric providers before exit ensures BatchSpanProcessor and PeriodicExportingMetricReader complete before the process exits.

## Verdict: PARTIAL

| Check | Status | Detail |
|-------|--------|--------|
| Provider identity (`must_have_any`) | ✅ | `agent_framework` expected to emit `gen_ai.provider.name` = "azure" or `gen_ai.system` via `ChatTelemetryLayer` |
| `service.name` | ✅ | Set to "microsoft-agent-framework" via `OTEL_SERVICE_NAME` |
| `gen_ai.request.model` | ✅ | Passed to `OpenAIChatCompletionClient`; emitted by `ChatTelemetryLayer` |
| `gen_ai.response.model` | ✅ | Returned by Azure API; emitted by `ChatTelemetryLayer` |
| `gen_ai.usage.input_tokens` | ✅ expected | `ChatTelemetryLayer` expected to emit modern token attributes from Azure response |
| `gen_ai.usage.output_tokens` | ✅ expected | As above |
| `gen_ai.agent.name` | ✅ | `Agent.run()` → `AgentTelemetryLayer` sets `gen_ai.agent.name` = "observability-haiku-agent" |
| `gen_ai.input.messages` | ✅ | `enable_sensitive_data=True` enables content capture |
| `gen_ai.output.messages` | ✅ | `enable_sensitive_data=True` enables content capture |
| `gen_ai.request.temperature` | ✅ | Passed via `default_options["temperature"]`; framework maps to span attribute |
| `gen_ai.conversation.id` | ✅ | UUID passed via `default_options["conversation_id"]`; framework maps to span attribute |
| `span.status_code` | ✅ | Emitted automatically by OTel SDK |
| Metrics pipeline | ✅ | `_configure_dynatrace_otlp()` sets metrics OTLP endpoint + delta temporality; `configure_otel_providers` initialises `MeterProvider` |
| `gen_ai.client.operation.duration` (metric) | ✅ expected | `MeterProvider` configured; `agent_framework` expected to record this OTel metric |
| `gen_ai.client.token.usage` (metric, AR-044) | ✅ expected | `MeterProvider` configured; `agent_framework` expected to record this metric |
| `gen_ai.token.type` (metric dimension) | ✅ expected | Metric dimension on `gen_ai.client.token.usage`; framework expected to emit `input`/`output` |
| Guardrails — Azure content filters | ❌ | No Azure Content Safety configured; `gen_ai.prompt.prompt_filter_results` (AR-015) and `gen_ai.completion.content_filter_results` (AR-016) will not be emitted |
| Guardrails — Bedrock | N/A | Not Bedrock |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity expected from `ChatTelemetryLayer` |
| Service health tile | ✅ | `span.status_code` auto-emitted by OTel SDK |
| Prompts — content | ✅ | `gen_ai.input.messages` + `gen_ai.output.messages` via `enable_sensitive_data=True` |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Prompts — conversation thread | ✅ | `gen_ai.conversation.id` set via `default_options` |
| Latency charts | ✅ expected | Metrics pipeline active; `gen_ai.client.operation.duration` expected |
| Cost dashboard (metric) | ✅ expected | `gen_ai.client.token.usage` metric expected; `gen_ai.token.type` dimension expected |
| Cost dashboard (span tokens) | ✅ expected | `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` expected from `ChatTelemetryLayer` |
| Agent quick filter | ✅ | `gen_ai.agent.name` = "observability-haiku-agent" set by `AgentTelemetryLayer` |
| Provider quick filter | ✅ | Provider identity present |
| Guardrail cards (Azure) | ❌ | Azure Content Safety not configured; AR-015/AR-016 absent |
| Guardrail cards (Bedrock) | N/A | Not Bedrock |
| Cache hit rate chart | N/A | Caching not used in this demo |

## Dashboard Coverage

| Dashboard View | Populated? | Missing attributes |
|----------------|------------|-------------------|
| Total requests | ✅ | — |
| Service health | ✅ | — |
| Avg / P99 latency (span-based) | ✅ | — |
| Latency charts (metric) | ✅ expected | Requires `gen_ai.client.operation.duration` metric from framework |
| Input token usage over time | ✅ expected | Requires `gen_ai.client.token.usage` metric with `gen_ai.token.type=input` |
| Output token usage over time | ✅ expected | Requires `gen_ai.client.token.usage` metric with `gen_ai.token.type=output` |
| Cost estimate | ✅ expected | Requires both metric and `gen_ai.token.type` dimension |
| Requests by provider | ✅ | — |
| Requests by model | ✅ | — |
| Agent vs LLM split | ✅ | `gen_ai.agent.name` present |
| Top agents by volume | ✅ | — |
| Recent prompts & completions | ✅ | Content capture enabled |
| Conversation threads | ✅ | `gen_ai.conversation.id` set |
| Azure content filter cards | ❌ | AR-015 / AR-016 absent — Azure Content Safety not configured |
| Evaluation results | ❌ | No evaluation bigevents emitted |
| Audit trail | ❌ | No audit bigevents emitted |

## Silent failures

| Attribute | Rule ID | Missing feature |
|-----------|---------|-----------------|
| `gen_ai.prompt.prompt_filter_results` | AR-015 | Azure content filter cards empty |
| `gen_ai.completion.content_filter_results` | AR-016 | Azure content filter cards empty |
| `gen_ai.evaluation.score.label` | AR-029 | Evaluation tab empty — no evaluation pipeline wired |

## What to fix in the example app

**1. Azure Content Safety guardrails (optional, demo scope)**

The demo does not configure Azure Content Safety, so AR-015/AR-016 will not be emitted. To populate the guardrail cards in `azureai.dashboard.json`, configure Azure Content Safety on the deployment and ensure `agent_framework` propagates the `prompt_filter_results` / `content_filter_results` fields from the Azure API response as span attributes.

**2. Verify `agent_framework` metric attribute names at runtime**

The analysis assumes `agent_framework` emits standard OTel semconv metric names (`gen_ai.client.operation.duration`, `gen_ai.client.token.usage` with `gen_ai.token.type` dimension). Confirm this by running the app and checking the DT metrics explorer — if the metrics arrive under different names, update the baseline and the dashboard DQL queries accordingly.

**3. No issues to fix in `app.py` itself**

- Metrics pipeline: correctly configured with delta temporality and explicit flush/shutdown.
- Agent name: correctly propagated via `Agent.run()` → `AgentTelemetryLayer`.
- Content capture: enabled via `enable_sensitive_data=True`.
- Conversation ID: correctly threaded via `default_options`.
- Temperature: correctly passed via `default_options`.
