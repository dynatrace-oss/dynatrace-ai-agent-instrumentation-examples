# Collector-side GenAI semconv enrichment

The same enrichment as [`../openpipeline/`](../openpipeline/), done **in transit** with an
OpenTelemetry Collector instead of **at ingest** with OpenPipeline. Pick whichever fits your
setup — the resulting spans, log events and GenAI metrics are equivalent.

| OpenPipeline | Collector equivalent |
|---|---|
| `spans-pipeline.json` processing stage | `transform/claude_code_genai` `trace_statements` |
| `spans-pipeline.json` `metricExtraction` stage | `signal_to_metrics` connector |
| `logs-pipeline.json` | `transform/claude_code_genai` `log_statements` |

| | OpenPipeline (`../openpipeline/`) | Collector (this directory) |
|---|---|---|
| Where it runs | Dynatrace, at ingest | Your infrastructure, before ingest |
| Extra components | none | an `otelcol-contrib` instance |
| Applies to | everything reaching the tenant, incl. clients you don't control | only traffic routed through this collector |
| Credentials | none extra | API token moves from every client into the collector |
| Change management | tenant settings (`builtin:openpipeline.spans.*`) | your collector config/deploy pipeline |

Use the collector variant when you already run one (common in fleets — one token in the
collector instead of in every developer's shell), or when you want the enriched spans to exist
identically across multiple backends. Use OpenPipeline when you want zero extra moving parts.

## Run

```bash
export DT_ENDPOINT="https://<env>.live.dynatrace.com"   # env-api host, not .apps.
export DT_API_TOKEN="dt0c01...."                        # OpenTelemetry ingest scope
otelcol-contrib --config config.yaml
```

Then point Claude Code at the collector (replacing the direct-to-Dynatrace endpoint from
`../setup.sh` — `OTEL_EXPORTER_OTLP_HEADERS` is no longer needed client-side):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

The `transform` processor and the `signal_to_metrics` connector are contrib-only — the core
`otelcol` distribution does not include them.

## Metrics

Claude Code exports only `claude_code.*` metrics, but the AI Observability *Token usage*,
*Average request duration* and *Overall cost* tiles read GenAI metrics. The `signal_to_metrics`
connector derives them from the spans the transform has just enriched, so the traces pipeline
exports to it and the metrics pipeline receives from it:

| Metric | Source span | Value |
|---|---|---|
| `gen_ai.client.token.usage` (legacy, keyed by `gen_ai.token.type`) | `claude_code.llm_request` | all four token fields |
| `gen_ai.client.inference.usage.input_tokens` | `claude_code.llm_request` | `input_tokens` |
| `gen_ai.client.inference.usage.output_tokens` | `claude_code.llm_request` | `output_tokens` |
| `gen_ai.client.inference.usage.cache_read.input_tokens` | `claude_code.llm_request` | `cache_read_tokens` |
| `gen_ai.client.inference.usage.cache_write.input_tokens` | `claude_code.llm_request` | `cache_creation_tokens` |
| `gen_ai.client.operation.duration` (histogram, seconds) | `claude_code.llm_request`, `claude_code.tool.execution` | span end − start |

See [`../openpipeline/README.md`](../openpipeline/README.md) for why both token conventions are
emitted and why the cache counters matter. Two collector-specific details:

- The connector can only select existing attribute keys, not rename them, so the transform also
  stages `error.type` (from `error_class`) on `claude_code.llm_request` and the tool child
  spans. That is the semconv attribute for a failed GenAI span, and
  it becomes the `error.type` dimension of the duration histogram.
- Constant dimensions such as `gen_ai.token.type` use `default_value` on a key the span does not
  carry.

Run **one** enrichment path. Applying both is harmless for span and log attributes, but every
GenAI metric is then counted twice.

## Known limitation (same as the OpenPipeline variant)

`gen_ai.input.messages` and `gen_ai.output.messages` are reconstructed from the raw
`user_prompt`, `prompt` and `response` attributes by escaping
backslashes, double quotes, and newlines. Prompts containing other JSON control characters
(tabs, carriage returns) are passed through unescaped — acceptable for the app's Prompts view,
but not a general-purpose JSON encoder. If Claude Code emits semconv-native message attributes
in a future release, both variants become unnecessary for that field.
