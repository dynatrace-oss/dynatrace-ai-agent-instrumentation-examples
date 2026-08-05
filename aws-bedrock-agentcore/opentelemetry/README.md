# Amazon Bedrock AgentCore — managed harness (`invoke_harness`) + OpenTelemetry

PoC for a specific, common scenario: your service is the **caller** of a fully-managed
[Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
harness — boto3's `invoke_harness` — and you don't own or deploy the harness's own
execution. You can't install OneAgent (or anything else) inside it.

> [!NOTE]
> This is different from [`aws-bedrock-agents/oneagent`](../../aws-bedrock-agents/oneagent),
> which demonstrates the *other* AgentCore path: a self-hosted LangGraph agent you deploy
> **into** AgentCore Runtime, where OneAgent auto-instruments the agent's own Bedrock calls
> from the inside. If you own the agent code running in AgentCore, use that approach instead —
> it needs zero manual instrumentation. This demo is for when you don't own that code, only
> the orchestrator that calls the managed harness.

## How it works

A FastAPI orchestrator (`server.py` / `main.py`) calls `boto3.client("bedrock-agentcore").invoke_harness(...)`,
wrapped in a manually created OpenTelemetry span following the
[GenAI semantic conventions](https://docs.dynatrace.com/docs/observe/dynatrace-for-ai-observability/get-started/opentelemetry):

```
FastAPI orchestrator (async handler -> asyncio.to_thread)
  └─ span "invoke_harness" (gen_ai.* attributes)
       └─ client.invoke_harness(harnessArn=..., traceParent=..., ...)
            └─ streamed response: contentBlockDelta* -> messageStop -> metadata
  └─ gen_ai.client.token.usage / gen_ai.client.operation.duration metrics
```

Three things this demo verifies concretely (checked against the `bedrock-agentcore`
botocore service model, `2024-02-28`), which weren't obvious from AWS's docs alone:

1. **`invoke_harness` is a real, distinct operation** (`InvokeHarness`), separate from
   `invoke_agent_runtime` (`InvokeAgentRuntime`) — AWS's own AgentCore observability guide
   only documents the latter.
2. **The response stream includes a `metadata` event with real token-usage and latency
   data** (`HarnessMetadataEvent.usage.{inputTokens,outputTokens,totalTokens}`,
   `HarnessMetadataEvent.metrics.latencyMs`) — so the caller genuinely can populate
   `gen_ai.usage.*` attributes from data the harness itself returns, no separate
   CloudWatch/X-Ray lookup needed for that part.
3. **`invoke_harness` takes W3C trace-context fields as first-class request parameters**
   (`traceParent`, `traceState`, `traceId`, `baggage`, mapped to the documented headers) —
   simpler than the AWS sample repo's approach for `invoke_agent_runtime`, which needs a
   boto3 event hook to inject headers manually.

## Metrics, not just span attributes

Setting `gen_ai.*` span attributes alone gets this call into the AI Observability app's
**Prompts/trace view** (its filter is attribute-presence-based: `isNotNull(gen_ai.system) or
isNotNull(gen_ai.provider.name)`). It does **not** reliably get it into the app's cost/token
**dashboards** — those read the `gen_ai.client.token.usage` / `gen_ai.client.operation.duration`
metrics, and for OTel-sourced telemetry (as opposed to OneAgent-sourced), the backend expects
those metrics to be emitted directly rather than derived server-side from span attributes.
That's why `main.py` emits them explicitly via the OTel Metrics API, the same way the
Traceloop-based [`aws-bedrock/opentelemetry`](../../aws-bedrock/opentelemetry) demo does for
the plain Bedrock Converse/Invoke APIs.

## What this does *not* solve

This gives you full caller-side visibility (latency, tokens, errors, trace correlation) for
the `invoke_harness` call itself. It does **not** give you spans for what happens *inside*
the harness (tool calls, reasoning steps, the underlying model call) — that requires either:

- AWS's own harness-side telemetry (CloudWatch Transaction Search + Tracing enabled on the
  harness resource — no code required, but a separate data path/UI from Dynatrace unless
  bridged), or
- Dynatrace's native [Bedrock AgentCore Hub extension](https://www.dynatrace.com/hub/detail/amazon-bedrock-agentcore-observability/)
  (GA'd Nov 2025) — **its exact coverage of the managed-harness case specifically is
  unverified as of this PoC** and should be confirmed against a real tenant before relying
  on it for this scenario.

The `traceParent` propagated in `invoke_harness()` at least means that if either of the above
does surface harness-side data, it shares the same W3C trace ID as this span, so the two views
can be correlated even if they can't be merged into one Dynatrace trace.

## Mapping to the "gen_ai attributes as custom request attributes" question

The `gen_ai.usage.input_tokens` / `output_tokens` set here are real OTel span attributes
(`span.set_attribute(...)`), not Dynatrace OneAgent SDK custom request attributes
(`addCustomRequestAttribute`). Custom request attributes live in a different data model and
are not confirmed to be visible to the app's `gen_ai.*`-attribute-driven matching — this demo
deliberately uses the officially documented mechanism instead.

## Running this demo

### Mock mode (no AWS credentials, no deployed harness)

```bash
make install
make run              # MOCK_AGENTCORE=true in .env.sample is on by default
make request          # in a second terminal
```

`MOCK_AGENTCORE=true` replays a synthetic stream shaped exactly like a real `InvokeHarness`
response (same event names/fields), so the full instrumentation path — span creation,
attribute setting, metric recording, trace-context propagation — runs and exports to
whatever OTLP endpoint you configure, without needing a real harness.

### Against a real harness

```bash
cp .env.sample .env
# set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION / HARNESS_ARN
# set MOCK_AGENTCORE=false
# set OTEL_EXPORTER_OTLP_*_ENDPOINT / DT_API_TOKEN to your Dynatrace environment
make install
make run
make request
```

### Verify in Dynatrace

```dql
fetch spans, from:now()-1h
| filter service.name == "aws-bedrock-agentcore-example"
| sort timestamp desc
| limit 50
```

```dql
timeseries sum(gen_ai.client.token.usage), by:{gen_ai.token.type}, from:-1h
| filter gen_ai.provider.name == "aws.bedrock_agentcore"
```

## CI: verifying OneAgent + OTel SDK coexistence

`test/e2e/aws_bedrock_agentcore_opentelemetry_test.go` (`TestAWSBedrockAgentCoreOpenTelemetryOneAgent`)
runs this demo in CI with OneAgent *also* installed on the runner, against the real e2e-test
Dynatrace tenant, with `MOCK_AGENTCORE=true` (no AgentCore harness exists in this AWS account
yet — see below). It asserts:

1. The manually created `gen_ai.provider.name == "aws.bedrock_agentcore"` span lands correctly
   (baseline attribute audit via the shared `GenericProfile`).
2. **The actual "does the combination work" check**: within the *same trace*, there is also a
   span with `dt.openpipeline.source == "oneagent"` — proving OneAgent's own auto-instrumentation
   of the FastAPI/Starlette layer and this app's manually created OTel SDK span end up correlated
   in one trace, rather than on two disjoint traces (or OneAgent dropping the request — see the
   sync-route thread-context bug this repo has hit before).
3. `gen_ai.client.operation.duration` reports data for the service (confirms the metrics path,
   not just spans).

This setup only exercises OneAgent's *unrelated* auto-instrumentation (FastAPI) coexisting with
our manual span — because `MOCK_AGENTCORE=true` means no real botocore call to the
`bedrock-agentcore` service ever happens, it cannot answer whether OneAgent has (or lacks) its
own dedicated sensor for that service. That remains open below.

## Open questions for a real deployment

- Confirm whether OneAgent's existing Bedrock GenAI sensor already covers the
  `bedrock-agentcore` boto3 client / `invoke_harness` before assuming manual instrumentation
  is required at all — it's a different botocore service ID than `bedrock-runtime`, so
  coverage isn't guaranteed just because the plain Bedrock sensor exists. **Not testable without
  a real harness** (this account currently lacks the AWS permissions to create one) — the CI
  combo test above uses `MOCK_AGENTCORE=true`, which never makes a real `bedrock-agentcore` API
  call, so it cannot exercise this.
- Confirm what the Dynatrace Bedrock AgentCore Hub extension actually ingests for a
  fully-managed-harness caller (CloudWatch-sourced built-in telemetry vs. requiring
  ADOT-in-agent-code, which isn't available to a caller who doesn't own the harness).
- `gen_ai.provider.name = "aws.bedrock_agentcore"` used here is a best-effort value chosen
  for this PoC, not a value confirmed against Dynatrace's semantic dictionary for this
  specific service — check before treating it as canonical.
