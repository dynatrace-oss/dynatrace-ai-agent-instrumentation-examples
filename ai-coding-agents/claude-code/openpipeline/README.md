# OpenPipeline enrichment for Claude Code spans

Maps Claude Code's beta tracing spans onto the [OpenTelemetry GenAI semantic
conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) at ingest, so
they fully populate the Dynatrace **AI Observability** app (token usage,
operations, agent topology, prompt stream). See the parent README section
"Light up the AI Observability app" for context.

Files:

- `spans-pipeline.json` — a custom span pipeline ("Claude Code GenAI") with three
  DQL processors: `claude_code.llm_request` → `chat` (+ `gen_ai.usage.*` tokens),
  `claude_code.interaction` → `invoke_agent` (+ agent name/id and
  `gen_ai.input.messages` built from `user_prompt`), `claude_code.tool` →
  `execute_tool` (+ `gen_ai.tool.name`).
- `spans-routing.json` — a routing entry sending all spans with
  `service.name == "claude-code"` through that pipeline.

## Apply with dtctl

Requires [dtctl](https://github.com/dynatrace-oss/dtctl) authenticated against
your environment, and permission to write settings objects for the
`builtin:openpipeline.spans.*` schemas.

```bash
# 1. Create the pipeline — note the settings object UID in the response
dtctl create settings -f spans-pipeline.json \
  --schema builtin:openpipeline.spans.pipelines --scope environment

# 2. Put that UID into spans-routing.json (replace <PIPELINE_OBJECT_UID>).
#    The UID is the UUID inside the returned objectId (also shown by
#    `dtctl get settings --schema builtin:openpipeline.spans.pipelines`).

# 3. Create the route
# DO NOT USE THIS COMMAND IF OTHER CUSTOM ROUTES EXIST ON THE TENANT
dtctl create settings -f spans-routing.json \
  --schema builtin:openpipeline.spans.routing --scope environment
```

Routing takes a minute or two to propagate; spans ingested in the meantime pass
through the default pipeline un-enriched.

## Apply manually instead

In the **OpenPipeline** app: **Spans → Pipelines → + Pipeline**, add three DQL
processors with the matchers and scripts from `spans-pipeline.json`, then under
**Dynamic routing** add a route with matcher
`matchesValue(service.name, "claude-code")` targeting the new pipeline.

## Notes

- `gen_ai.input.messages` is only populated when `OTEL_LOG_USER_PROMPTS=1` is
  set; otherwise Claude Code redacts the `user_prompt` span attribute.
- The processors only *add* attributes — original span data is unchanged, and
  spans from other services are not touched.
- To undo, delete the two settings objects (routing first, then the pipeline).
