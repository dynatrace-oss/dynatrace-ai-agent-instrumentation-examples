# Collector-side GenAI semconv enrichment

The same span enrichment as [`../openpipeline/`](../openpipeline/), done **in transit** with an
OpenTelemetry Collector instead of **at ingest** with OpenPipeline. Pick whichever fits your
setup — the resulting spans are identical.

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

The `transform` processor is contrib-only — the core `otelcol` distribution does not include it.

## Known limitation (same as the OpenPipeline variant)

`gen_ai.input.messages` is reconstructed from the raw `user_prompt` attribute by escaping
backslashes, double quotes, and newlines. Prompts containing other JSON control characters
(tabs, carriage returns) are passed through unescaped — acceptable for the app's Prompts view,
but not a general-purpose JSON encoder. If Claude Code emits semconv-native message attributes
in a future release, both variants become unnecessary for that field.
