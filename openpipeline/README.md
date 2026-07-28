# Cross-cutting OpenPipeline configs

OpenPipeline configs here apply tenant-wide, across multiple demos, rather than belonging to one `<sdk>/<instrumentation>/` directory. Per-demo OpenPipeline configs (e.g. `langfuse/opentelemetry/openpipeline-langfuse.yaml`, `langgraph/oneagent/openpipeline-langgraph.yaml`) stay next to the demo they belong to.

## `openpipeline-oneagent-genai-metrics.yaml`

Backfills `gen_ai.client.token.usage` and `gen_ai.client.operation.duration` for every OneAgent demo that doesn't already ship its own OpenPipeline config: `anthropic`, `cohere`, `groq`, `haystack`, `mistral`, `ollama`, `openai`, `aws-bedrock`, `aws-bedrock-agents`, `aws-strands` (all `*/oneagent`).

OneAgent auto-instrumentation captures `gen_ai.*` span attributes but emits neither metric — there's no collector in front of it to derive them from. Both are recoverable tenant-side from attributes OneAgent already sets on the span; see the file's header comment for the extraction pattern (and why the token-usage metric needs two extractors instead of one).

`langgraph/oneagent` is the one OneAgent demo **not** covered by this file — it already has a more specific, higher-priority routing entry for its own pipeline (secret redaction), and OpenPipeline routing is first-match, not fan-out, so its spans never reach this generic pipeline. Its copy of the same three metric extractors lives in `langgraph/oneagent/openpipeline-langgraph.yaml` instead.

Deploy with `dtctl` (see the file's header comment for the exact matcher/routing entry to add):

```bash
dtctl create settings -f openpipeline/openpipeline-oneagent-genai-metrics.yaml \
  --schema builtin:openpipeline.spans.pipelines --scope environment
```
