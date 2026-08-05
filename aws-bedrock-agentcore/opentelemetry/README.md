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

## Dynatrace prerequisites

This demo requires **OneAgent installed on the host**, plus one tenant setting that is
**off by default**:

> **Settings → Collect and capture → General monitoring settings → OneAgent features →
> "OpenTelemetry (Python) [Opt-In]"** — enable it.
>
> Docs: [OneAgent and OpenTelemetry — configuration, Python prerequisites](https://docs.dynatrace.com/docs/ingest-from/dynatrace-oneagent/oneagent-and-opentelemetry/configuration#prereq--python)

Without this setting, OneAgent never intercepts the manually created span in `main.py` at all —
and since this app has no OTel SDK exporter of its own (see below), that span is then silently
dropped, not merely disconnected. There is no fallback path.

## How it works

A FastAPI orchestrator (`server.py` / `main.py`) calls `boto3.client("bedrock-agentcore").invoke_harness(...)`,
wrapped in a span created via the **plain OpenTelemetry API** — `opentelemetry.trace.get_tracer(...)`,
`start_as_current_span(...)`, `set_attribute(...)` — following the
[GenAI semantic conventions](https://docs.dynatrace.com/docs/observe/dynatrace-for-ai-observability/get-started/opentelemetry):

```
FastAPI orchestrator (async handler -> asyncio.to_thread)
  └─ OneAgent auto-instruments "POST /invoke" (HTTP entry span)
       └─ span "invoke_harness" (gen_ai.* attributes) -- plain OTel API, no SDK, no exporter
            └─ client.invoke_harness(harnessArn=..., traceParent=..., ...)
                 └─ streamed response: contentBlockDelta* -> messageStop -> metadata
```

**Deliberately no `opentelemetry-sdk`, no exporter, no `TracerProvider`.** An earlier version of
this PoC configured its own OTLP exporter pointed directly at Dynatrace. That turned out to be
actively wrong here, not just redundant — see "Why there's no OTel SDK in this app" below.

Three things about `invoke_harness` itself this demo verifies concretely (checked against the
`bedrock-agentcore` botocore service model, `2024-02-28`), which weren't obvious from AWS's docs
alone:

1. **`invoke_harness` is a real, distinct operation** (`InvokeHarness`), separate from
   `invoke_agent_runtime` (`InvokeAgentRuntime`) — AWS's own AgentCore observability guide
   only documents the latter.
2. **The response stream includes a `metadata` event with real token-usage and latency
   data** (`HarnessMetadataEvent.usage.{inputTokens,outputTokens,totalTokens}`,
   `HarnessMetadataEvent.metrics.latencyMs`) — so the caller genuinely can populate
   `gen_ai.usage.*` attributes from data the harness itself returns, no separate
   CloudWatch/X-Ray lookup needed for that part. The harness runs an internal agent loop
   (`maxIterations`), and the schema does not guarantee a single `metadata` event per
   invocation, so `main.py` accumulates across events rather than overwriting.
3. **`invoke_harness` takes W3C trace-context fields as first-class request parameters**
   (`traceParent`, `traceState`, `traceId`, `baggage`, mapped to the documented headers) —
   simpler than the AWS sample repo's approach for `invoke_agent_runtime`, which needs a
   boto3 event hook to inject headers manually.

## Why there's no OTel SDK in this app

Found empirically while building the CI verification below: once OneAgent's `OpenTelemetry (Python)` opt-in is
enabled, **OneAgent intercepts `start_as_current_span()` calls directly** and creates its own
correctly-correlated span for them — as a real child of the incoming HTTP request, sharing
OneAgent's own trace ID. This happens purely from the plain `opentelemetry-api` calls; no SDK,
no `TracerProvider`, no exporter needed on the app's side at all.

Configuring the app's *own* SDK `TracerProvider` + OTLP exporter **on top of that does not get
replaced or blocked** — it runs in parallel, as a second, fully independent pipeline. The result,
confirmed directly in Dynatrace: the exact same `invoke_harness()` call produced **two separate
span records**, 0.7ms apart — one correctly correlated (`dt.openpipeline.source: oneagent`, same
trace as OneAgent's `POST /invoke`), and one disconnected duplicate (`dt.openpipeline.source:
/api/v2/otlp/v1/traces`, its own unrelated trace ID), because the app's own SDK pipeline has no
visibility into OneAgent's separately-tracked context.

Dropping the app's own exporter entirely and relying only on the API removes the duplicate and
keeps the correlated copy — which is what this version of the app does.

**Tradeoff:** this app now produces literally zero telemetry without OneAgent (and that opt-in
setting) present. If you need this code to also work standalone against a plain OTel Collector —
e.g. for local development without OneAgent — that requires reintroducing an SDK/exporter behind
a flag, and you'd need to decide how to avoid reproducing the same duplication when OneAgent
*is* also present.

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

Requires OneAgent installed on the host with the `OpenTelemetry (Python) [Opt-In]` feature
enabled (see [Dynatrace prerequisites](#dynatrace-prerequisites) above) — without it, this app
produces no telemetry at all, regardless of mock vs. real mode below.

### Mock mode (no AWS credentials, no deployed harness)

```bash
make install
make run              # MOCK_AGENTCORE=true in .env.sample is on by default
make request          # in a second terminal
```

`MOCK_AGENTCORE=true` replays a synthetic stream shaped exactly like a real `InvokeHarness`
response (same event names/fields), so the full instrumentation path — span creation,
attribute setting, metric recording, trace-context propagation — runs without needing a real
harness.

### Against a real harness

```bash
cp .env.sample .env
# set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION / HARNESS_ARN
# set MOCK_AGENTCORE=false
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

## CI: verifying OneAgent captures and correlates the manual span

`test/e2e/aws_bedrock_agentcore_opentelemetry_test.go` (`TestAWSBedrockAgentCoreOpenTelemetryOneAgent`)
runs this demo in CI with OneAgent installed on the runner (with the opt-in feature enabled on
the tenant), against the real e2e-test Dynatrace tenant, with `MOCK_AGENTCORE=true` (no
AgentCore harness exists in this AWS account yet — see below). It asserts:

1. The manually created `gen_ai.provider.name == "aws.bedrock_agentcore"` span lands correctly
   (baseline attribute audit via the shared `GenericProfile`).
2. **The trace contains at least 2 spans** (OneAgent's own HTTP entry span + the manually
   created `invoke_harness` span) **and every span in it is OneAgent-sourced** — this app has
   no other export path, so a non-OneAgent-sourced span, or the manual span missing/on its own
   trace, means OneAgent silently failed to capture it.
3. **No disconnected duplicate exists** — a regression check specifically for the bug described
   above (an earlier version of this app produced exactly this: a second `invoke_harness` span,
   same name, different trace, non-`oneagent` source).
4. `gen_ai.client.operation.duration` reports data for the service — this also answers whether
   OneAgent's opt-in captures *metric* instruments the same way it captures spans, which wasn't
   confirmed independently of this test.

This setup only exercises OneAgent's *unrelated* auto-instrumentation (FastAPI) plus its
OpenTelemetry interception of the manual span — because `MOCK_AGENTCORE=true` means no real
botocore call to the `bedrock-agentcore` service ever happens, it cannot answer whether OneAgent
has (or lacks) its own dedicated sensor for that service. That remains open below.

## Open questions for a real deployment

- Confirm whether OneAgent's existing Bedrock GenAI sensor already covers the
  `bedrock-agentcore` boto3 client / `invoke_harness` before assuming manual instrumentation
  is required at all — it's a different botocore service ID than `bedrock-runtime`, so
  coverage isn't guaranteed just because the plain Bedrock sensor exists. **Not testable without
  a real harness** (this account currently lacks the AWS permissions to create one) — the CI
  test above uses `MOCK_AGENTCORE=true`, which never makes a real `bedrock-agentcore` API
  call, so it cannot exercise this.
- Confirm what the Dynatrace Bedrock AgentCore Hub extension actually ingests for a
  fully-managed-harness caller (CloudWatch-sourced built-in telemetry vs. requiring
  ADOT-in-agent-code, which isn't available to a caller who doesn't own the harness).
- `gen_ai.provider.name = "aws.bedrock_agentcore"` used here is a best-effort value chosen
  for this PoC, not a value confirmed against Dynatrace's semantic dictionary for this
  specific service — check before treating it as canonical.
- Whether OneAgent's default entry-point behavior (per the OpenTelemetry-Python docs, "OneAgent
  ingests by default only spans with a span kind of `Server` or `Consumer`") really doesn't
  matter here for a `CLIENT`-kind child span nested under an already-recognized `Server`-kind
  span, or whether that restriction only governs which spans can start a *new* trace — the CI
  test above confirms our `CLIENT`-kind span gets captured in practice, but the exact boundary
  of that default isn't independently confirmed from the docs alone.
