# Collector-side GenAI semconv enrichment

This OpenTelemetry Collector configuration maps Claude Code telemetry onto the
[OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
in transit, so it fully populates the Dynatrace AI Observability app.

`config.yaml` contains:

- `transform/claude_code_genai` `trace_statements`: span mappings.
- `transform/claude_code_genai` `log_statements`: mappings for the `assistant_response` and
  `user_prompt` log events, including `gen_ai.output.messages`.
- the `signal_to_metrics` connector: GenAI metrics derived from the enriched spans.

Running a collector also keeps the API token in one place instead of in every developer's shell.

## Run

```bash
export DT_ENDPOINT="https://<env>.live.dynatrace.com"   # env-api host, not .apps.
export DT_API_TOKEN="dt0c01...."                        # OpenTelemetry ingest scope
otelcol-contrib --config config.yaml
```

Then point Claude Code at the collector. `OTEL_EXPORTER_OTLP_HEADERS` is no longer needed
client-side:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

The `transform` processor and the `signal_to_metrics` connector are contrib-only. The core
`otelcol` distribution does not include them.

## Span mappings

- `claude_code.llm_request` becomes `chat`, with models and `gen_ai.usage.*` tokens.
- `claude_code.interaction` becomes `invoke_agent`, with agent identity and
  `gen_ai.input.messages` built from `user_prompt`.
- `claude_code.tool` becomes `execute_tool`, with `gen_ai.tool.name`.
- `claude_code.tool.execution` and `claude_code.tool.blocked_on_user` get conversation
  correlation only. They get no operation name, because typing them as `execute_tool` would
  count every tool call three times.

`session.id` is mapped to `gen_ai.conversation.id`. `gen_ai.usage.total_tokens` is the sum of
input and output tokens. It does not drive the app's Token usage tile; the metrics below do.

## Metrics

The AI Observability *Token usage*, *Average request duration* and *Overall cost* tiles are
metric-backed. Claude Code exports only `claude_code.*` metrics, so enriching spans alone
leaves those tiles empty. The `signal_to_metrics` connector derives the GenAI metrics from the
spans the transform has just enriched. The traces pipeline exports to it and the metrics
pipeline receives from it:

| Metric | Source span | Value |
|---|---|---|
| `gen_ai.client.token.usage` (legacy, keyed by `gen_ai.token.type`) | `claude_code.llm_request` | all four token fields |
| `gen_ai.client.inference.usage.input_tokens` | `claude_code.llm_request` | `input_tokens` |
| `gen_ai.client.inference.usage.output_tokens` | `claude_code.llm_request` | `output_tokens` |
| `gen_ai.client.inference.usage.cache_read.input_tokens` | `claude_code.llm_request` | `cache_read_tokens` |
| `gen_ai.client.inference.usage.cache_write.input_tokens` | `claude_code.llm_request` | `cache_creation_tokens` |
| `gen_ai.client.operation.duration` (histogram, seconds) | `claude_code.llm_request`, `claude_code.tool.execution` | span end minus start |

### Why both token conventions are emitted

The GenAI token metrics were restructured. The current
[specification](https://github.com/open-telemetry/semantic-conventions-genai) has no
`gen_ai.client.token.usage` and no `gen_ai.token.type`. It defines one counter per token kind.

The AI Observability tiles still read the legacy key. Emitting only the current names would
leave the tiles empty, so both are emitted on purpose. Drop the legacy entries once the app
reads the current names. The spec also defines
`gen_ai.client.inference.usage.reasoning.output_tokens`. It is omitted because Claude Code
spans carry no reasoning token count.

Cache counters matter. Prompt caching dominates token volume for a coding agent: one real
request showed 338,966 cache read tokens against 2 input tokens. Counting only input and
output understates usage by orders of magnitude.

### Dimensions and errors

- Failures are expressed as the `error.type` dimension on the duration histogram, as the spec
  asks. The connector can only select existing keys, not rename them, so the transform stages
  `error.type` from `error_class` on `claude_code.llm_request` and the tool child spans.
  `error_class` holds low-cardinality exception names such as `ShellError`.
- Constant dimensions such as `gen_ai.token.type` use `default_value` on a key the span does
  not carry.
- Do not add `session.id` or `gen_ai.conversation.id` as metric dimensions. Both are
  effectively unbounded.

### The stock error tiles stay empty

*Invocation error count*, *Failure rate* and *Error rate over time* read
`dt.service.request.failure_count`, which comes from `server` or `consumer` entry-point
spans. Every Claude Code span is `internal`, so those tiles stay empty and Failure rate shows
0% meaning no measurements. Use the `error.type` dimension on
`gen_ai.client.operation.duration` instead.

## Correlate the response log back to the span

Claude Code never puts assistant text on a span. It emits it in the `response` attribute of
the `assistant_response` log event, which the log statements map to `gen_ai.output.messages`.
Join it back with one of two keys:

| Log field | Matches | Granularity |
|---|---|---|
| `span_id` | `claude_code.interaction` | the whole user turn |
| `request_id` | `claude_code.llm_request` | one API call |

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

When joining on `span_id`, cast first: `span.id` is a uid on spans and `span_id` is a string
on logs. Comparing them directly returns zero rows with no error. Use `toString(span.id)`.

This does not fill the Output column of the AI Observability prompt stream, which reads spans
only.

## Telemetry attributes and privacy

Claude Code attaches `user.email`, `user.id`, `user.account_uuid`, `organization.id` and
`session.id` to its telemetry. Account UUID and session ID inclusion in metrics are on by
default. Set `OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false` and
`OTEL_METRICS_INCLUDE_SESSION_ID=false` to remove them from metrics. Dropping `session.id`
also removes the source of `gen_ai.conversation.id`.

`gen_ai.input.messages` is populated only when `OTEL_LOG_USER_PROMPTS=1`. That captures prompt
content and can expose sensitive data, so enable it only when approved.

## Known limitation

`gen_ai.input.messages` and `gen_ai.output.messages` are built from the raw `user_prompt`,
`prompt` and `response` attributes by escaping backslashes, double quotes, and newlines. Other
JSON control characters (tabs, carriage returns) pass through unescaped. That is fine for the
app's Prompts view but is not a general-purpose JSON encoder. If Claude Code emits
semconv-native message attributes in a future release, this mapping becomes unnecessary for
that field.
