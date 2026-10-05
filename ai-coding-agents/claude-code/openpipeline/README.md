# OpenPipeline enrichment for Claude Code spans

Maps Claude Code's beta tracing spans onto the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) at ingest, so they fully populate the Dynatrace **AI Observability** app, including token usage, operations, agent topology, and the prompt stream.

See the parent README section **Light up the AI Observability app** for context.

Files:

- `spans-pipeline.json` — a custom span pipeline named **Claude Code GenAI** with three DQL processors:
  - `claude_code.llm_request` → `chat`, including models and `gen_ai.usage.*` tokens.
  - `claude_code.interaction` → `invoke_agent`, including agent identity and `gen_ai.input.messages` built from `user_prompt`.
  - `claude_code.tool` → `execute_tool`, including `gen_ai.tool.name`.
- `spans-routing.json` — an example routing entry that sends spans with `service.name == "claude-code"` through the custom pipeline.

The processors also map `session.id` to `gen_ai.conversation.id`. Native Claude Code attributes such as `gen_ai.response.id` and `gen_ai.response.finish_reasons` pass through unchanged.

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

## Create the pipeline manually instead

If you do not want to use `dtctl`, recreate the complete setup in the **OpenPipeline** app:

1. Open **Spans → Pipelines → + Pipeline**.
2. Name it **Claude Code GenAI**.
3. Add the three DQL processors using the matchers and scripts from `spans-pipeline.json`.
4. Open **Spans → Dynamic routing**.
5. Add a route with matcher `matchesValue(service.name, "claude-code")` targeting the new pipeline.
6. Save without deleting or replacing other routes.

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
| filter in(span.name, array("claude_code.interaction", "claude_code.llm_request", "claude_code.tool"))
| fields start_time, trace.id, span.id, span.parent_id, span.name,
    gen_ai.operation.name, gen_ai.provider.name, gen_ai.system,
    gen_ai.agent.name, gen_ai.request.model, gen_ai.response.model,
    gen_ai.usage.input_tokens, gen_ai.usage.output_tokens,
    gen_ai.conversation.id, dt.openpipeline.pipelines
| sort start_time desc
```

Expected operation mappings:

| Claude Code span | `gen_ai.operation.name` |
|---|---|
| `claude_code.interaction` | `invoke_agent` |
| `claude_code.llm_request` | `chat` |
| `claude_code.tool` | `execute_tool` |

Spans should show the custom pipeline in `dt.openpipeline.pipelines` and a non-null `gen_ai.operation.name`.

Interpretation:

- No Claude Code spans: trace export or OTLP ingestion is not working.
- Spans exist but `gen_ai.operation.name` is null: the route did not select the custom pipeline, the pipeline is disabled, or routing has not propagated.
- Interaction and LLM spans exist, but their IDs do not form a parent-child relationship: investigate Claude Code trace-context propagation rather than OpenPipeline fields processing.
- The mappings and hierarchy are present: refresh AI Observability and verify its selected timeframe.
