# OpenPipeline enrichment for Claude Code telemetry

Maps Claude Code's beta tracing spans onto the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) at ingest, so they fully populate the Dynatrace **AI Observability** app, including token usage, operations, agent topology, and the prompt stream.

See the parent README section **Light up the AI Observability app** for context.

Files:

- `spans-pipeline.json` — a custom span pipeline named **Claude Code GenAI** with four DQL processors:
  - `claude_code.llm_request` → `chat`, including models and `gen_ai.usage.*` tokens.
  - `claude_code.interaction` → `invoke_agent`, including agent identity and `gen_ai.input.messages` built from `user_prompt`.
  - `claude_code.tool` → `execute_tool`, including `gen_ai.tool.name`.
  - `claude_code.tool.execution` and `claude_code.tool.blocked_on_user` → conversation correlation only, with no operation name.
- `spans-routing.json` — an example routing entry that sends spans with `service.name == "claude-code"` through the custom pipeline.
- `logs-pipeline.json` — a custom log pipeline named **Claude Code GenAI (logs)** that maps the `assistant_response` and `user_prompt` log events onto the same conventions, including `gen_ai.output.messages`.
- `logs-routing.json` — an example log routing entry for that pipeline.

The processors also map `session.id` to `gen_ai.conversation.id`. Native Claude Code attributes such as `gen_ai.response.id` and `gen_ai.response.finish_reasons` pass through unchanged.

Two details are worth calling out, because both were wrong in an earlier revision of this example:

- `gen_ai.usage.total_tokens` is computed as the sum of the input and output tokens, completing the span-side token mapping for anything querying spans directly. It does **not** drive the app's Token usage tile; see the metrics section below for what does.
- Claude Code emits `claude_code.tool.execution` and `claude_code.tool.blocked_on_user` as children of `claude_code.tool`. The matcher `matchesValue(span.name, "claude_code.tool")` is an exact match and does not cover them. They are correlated to the conversation but deliberately left without a `gen_ai.operation.name`, because typing them as `execute_tool` would count every tool call three times.

## Create the pipeline with dtctl

Creating the pipeline as its own settings object is safe and does not replace the tenant's routing configuration.

This requires [dtctl](https://github.com/dynatrace-oss/dtctl), authentication against the target environment, and permission to write settings objects for `builtin:openpipeline.spans.pipelines`.

```bash
dtctl create settings -f spans-pipeline.json \
  --schema builtin:openpipeline.spans.pipelines \
  --scope environment
```

## Add the route in the OpenPipeline app

> [!WARNING]
> Do not submit `spans-routing.json` directly with `dtctl create settings` on a tenant that may already have custom span routes. Span routing is tenant-wide. Replacing the routing settings object can remove unrelated routes, alter route ordering, or redirect other services.

In the **OpenPipeline** app:

1. Open **Spans → Dynamic routing**.
2. Review the existing routes and their order.
3. Add a route with matcher:

   ```text
   matchesValue(service.name, "claude-code")
   ```

4. Select the **Claude Code GenAI** pipeline created above.
5. Enable and save the route without removing the existing entries.

Routing can take a minute or two to propagate. Spans ingested before propagation pass through the previously selected pipeline and are not retroactively enriched.

If routing must be automated, first read or export the tenant's current routing settings, merge the Claude Code entry into the existing `routingEntries` array, review the full merged object, and then update it. Do not treat the bundled `spans-routing.json` as the complete desired routing state for an existing tenant.

## Enrich the assistant response with the log pipeline

Claude Code never attaches assistant text to a span. It emits the text in the `response` attribute of the `claude_code.assistant_response` log event, so no span pipeline can populate `gen_ai.output.messages`. OpenPipeline processes each signal independently and cannot join a log onto a span at ingest. `logs-pipeline.json` therefore maps the log events themselves onto the GenAI conventions.

Creating the log pipeline is its own settings object and is as safe as the span pipeline:

```bash
dtctl create settings -f logs-pipeline.json \
  --schema builtin:openpipeline.logs.pipelines \
  --scope environment
```

> [!WARNING]
> The routing caution above applies here too, and log routing is usually the busier of the two. A tenant that ingests security or platform log sources can carry many enabled entries in one tenant-wide object, and replacing it wholesale removes them all. Add the entry under **Logs → Dynamic routing** in the OpenPipeline app, or export the current routing object, append one entry to `routingEntries`, review the merged result, and update it.

This needs `OTEL_LOG_ASSISTANT_RESPONSES=1`, plus `OTEL_LOG_USER_PROMPTS=1` for the prompt half. Read the prompt-content warning below before enabling either.

### Correlate the response log back to the span

The response log and the LLM span share `request_id`. That is the reliable join key:

```dql
fetch spans, from:now()-1h
| filter span.name == "claude_code.llm_request"
| fields request_id, gen_ai.conversation.id, gen_ai.usage.total_tokens
| join [
    fetch logs, from:now()-1h
    | filter event.name == "assistant_response"
    | fields request_id, gen_ai.output.messages
  ], on:{left[request_id] == right[request_id]}, fields:{gen_ai.output.messages}
```

> [!NOTE]
> Do not join on `span_id`. These log events carry a `span_id`, but it does not correspond to any exported Claude Code span, and many log events share one value. Joining on it returns no rows.
>
> Note also that the log field is `event.name == "assistant_response"`, without the `claude_code.` prefix. The prefixed form appears in `content`, not in `event.name`.

This enrichment makes the response queryable and joinable as GenAI-shaped data. It does not fill the **Output** column of the AI Observability prompt stream, which reads spans only. Populating that column would require the response to be on the span itself, which is an upstream Claude Code instrumentation change.

## Create the pipeline manually instead

If you do not want to use `dtctl`, recreate the complete setup in the **OpenPipeline** app:

1. Open **Spans → Pipelines → + Pipeline**.
2. Name it **Claude Code GenAI**.
3. Add the four DQL processors using the matchers and scripts from `spans-pipeline.json`.
4. Open **Spans → Dynamic routing**.
5. Add a route with matcher `matchesValue(service.name, "claude-code")` targeting the new pipeline.
6. Save without deleting or replacing other routes.

## Emit the GenAI metrics the app tiles read

The **Token usage**, **Average request duration** and **Overall cost** tiles are metric-backed, not span-backed. They read the OpenTelemetry GenAI semantic convention metrics, chiefly `gen_ai.client.token.usage` and `gen_ai.client.operation.duration`. Enriching spans alone therefore leaves those tiles showing *No data available* even while the table beside them reports a healthy token count from the same spans.

Claude Code cannot close this gap on its own. It exports eight metrics, all named `claude_code.*`, and its documentation states that no GenAI semantic convention metrics are exported. Its *span* attributes do follow the conventions, which is why the span mapping works while the metrics do not.

`spans-pipeline.json` therefore carries a `metricExtraction` stage next to the `processing` stage, which derives the semconv metrics from the spans already being enriched:

### Both token conventions are emitted, on purpose

The GenAI token metrics were restructured. The current [specification](https://github.com/open-telemetry/semantic-conventions-genai) has no `gen_ai.client.token.usage` and no `gen_ai.token.type` attribute. It defines one counter per token kind instead.

The AI Observability tiles still read the legacy key. Emitting only the current names would be conformant and would leave the tiles empty, which defeats the point of this example. So the stage emits both, and this is deliberate rather than an oversight:

| Metric | Convention | Source field |
|---|---|---|
| `gen_ai.client.token.usage` | legacy, keyed by `gen_ai.token.type` | all four token fields |
| `gen_ai.client.inference.usage.input_tokens` | current | `input_tokens` |
| `gen_ai.client.inference.usage.output_tokens` | current | `output_tokens` |
| `gen_ai.client.inference.usage.cache_read.input_tokens` | current | `cache_read_tokens` |
| `gen_ai.client.inference.usage.cache_write.input_tokens` | current | `cache_creation_tokens` |
| `gen_ai.client.operation.duration` | current, histogram in **seconds** | derived, see below |

Drop the legacy processors once the app reads the current names. The spec also defines `gen_ai.client.inference.usage.reasoning.output_tokens`, which is omitted because Claude Code spans carry no reasoning token count; emitting a zero would be worse than emitting nothing.

Prompt caching dominates token volume for a coding agent. On a real session, a single request showed 338,966 cache read tokens against 2 input tokens, so extracting only input and output understates usage by orders of magnitude.

### Duration must be in seconds, and two field traps

The spec requires `gen_ai.client.operation.duration` in seconds. Dynatrace's built-in `measurement: duration` emits **microseconds**, which reports a 10 second call as 10,879,245. The stage therefore derives the value in the processing stage and feeds the histogram from that field instead.

The derivation must use `duration / 1s`, not `duration_ms`. `duration_ms` exists at query time but is **not available during ingest processing**, so a processor referencing it silently produces nothing: the field is simply absent on the ingested span, and the metric never appears. There is no error anywhere.

Errors follow the convention too. OTel expresses GenAI failures as an `error.type` dimension on the duration histogram rather than a separate error counter, so error counts are derived by filtering that metric. `error.type` is sourced from the span's `error_class`, whose values are canonical exception names such as `ShellError` and `McpToolCallError`, exactly the low-cardinality identifier the spec asks for. The free-text `error` field is deliberately not used as a dimension.

Dimensions are deliberately limited to model, provider and operation. Do not add `session.id` or `gen_ai.conversation.id` as metric dimensions: both are effectively unbounded and would create a cardinality problem.

> [!NOTE]
> A `dtctl apply --dry-run` does not validate these payloads fully. A duration histogram requires `sampling` to be `enabled`, and the dry run reports success before the real apply rejects it. Treat the first non-dry apply as the real validation step.

### The stock error tiles cannot be filled

**Invocation error count**, **Failure rate** and **Error rate over time** read `dt.service.request.failure_count`, joined to the GenAI service through Smartscape. That metric is derived from entry-point spans of `server` or `consumer` kind.

Every Claude Code span is `span.kind: internal`, without exception. No request count or failure count is ever produced for the service, so those tiles stay empty and Failure rate reads a confident 0% that means *no measurements*, not *no errors*.

No pipeline can change this. A processor cannot turn an internal span into an entry point, and manufacturing request counts for an agent that serves no inbound requests would be dishonest. Use the `error.type` dimension on `gen_ai.client.operation.duration` instead, which reflects real failures.

## Telemetry attributes and privacy

Claude Code attaches a standard attribute set to every metric, span and log event it exports, including `user.email`, `user.id`, `user.account_uuid`, `organization.id` and `session.id`. Account UUID and session id inclusion are on by default.

None of that is introduced by this pipeline, but it does end up in your tenant, so decide it deliberately rather than by default. The relevant switches are `OTEL_METRICS_INCLUDE_ACCOUNT_UUID`, `OTEL_METRICS_INCLUDE_SESSION_ID`, `OTEL_METRICS_INCLUDE_VERSION`, `OTEL_METRICS_INCLUDE_ENTRYPOINT`, `OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES` and `OTEL_METRICS_INCLUDE_REPOSITORY`. Setting the first two to `false` removes the per-user identifiers from metrics and lowers cardinality at the same time. Note that dropping `session.id` also removes the key this pipeline maps to `gen_ai.conversation.id`, so conversation grouping goes with it.

## Choose one enrichment path

Use either:

- **OpenPipeline enrichment** for Claude Code spans sent directly to Dynatrace, or
- **Collector enrichment** when Claude Code sends telemetry through the provided OpenTelemetry Collector configuration.

Applying both is redundant. The mappings intentionally use the same values so both paths produce equivalent GenAI attributes.

The repository E2E test uses the **Collector path**. This OpenPipeline configuration is the customer-facing alternative and does not control that E2E test.

## Prompt-content warning

`gen_ai.input.messages` is populated only when Claude Code emits `user_prompt`.

Enabling `OTEL_LOG_USER_PROMPTS=1` captures prompt content and can expose source code, credentials, personal data, or other sensitive information. Leave it disabled unless message-content capture has been explicitly approved.

The remaining processors still work when `user_prompt` is absent.

## Verify

After saving the pipeline and route, run a new Claude Code interaction and query the newly ingested spans:

```dql
fetch spans, from:now()-1h
| filter service.name == "claude-code"
| filter in(span.name, array("claude_code.interaction", "claude_code.llm_request", "claude_code.tool", "claude_code.tool.execution", "claude_code.tool.blocked_on_user"))
| fields start_time, trace.id, span.id, span.parent_id, span.name,
    gen_ai.operation.name, gen_ai.provider.name, gen_ai.system,
    gen_ai.agent.name, gen_ai.request.model, gen_ai.response.model,
    gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, gen_ai.usage.total_tokens,
    gen_ai.conversation.id, dt.openpipeline.pipelines
| sort start_time desc
```

Expected operation mappings:

| Claude Code span | `gen_ai.operation.name` |
|---|---|
| `claude_code.interaction` | `invoke_agent` |
| `claude_code.llm_request` | `chat` |
| `claude_code.tool` | `execute_tool` |
| `claude_code.tool.execution` | none, correlated only |
| `claude_code.tool.blocked_on_user` | none, correlated only |

Spans should show the custom pipeline in `dt.openpipeline.pipelines`. The first three span types should carry a non-null `gen_ai.operation.name`; the two tool child spans carry `gen_ai.conversation.id` but no operation name, by design.

Interpretation:

- No Claude Code spans: trace export or OTLP ingestion is not working.
- Spans exist but `gen_ai.operation.name` is null: the route did not select the custom pipeline, the pipeline is disabled, or routing has not propagated.
- Interaction and LLM spans exist, but their IDs do not form a parent-child relationship: investigate Claude Code trace-context propagation rather than OpenPipeline fields processing.
- The mappings and hierarchy are present: refresh AI Observability and verify its selected timeframe.
