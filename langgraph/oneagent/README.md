# LangGraph + OneAgent

This sample traces a [LangGraph](https://langchain-ai.github.io/langgraph/) agent with Dynatrace using **OneAgent auto-instrumentation** — no manual OpenTelemetry export or collector. OneAgent instruments the underlying Azure OpenAI SDK calls the graph makes and ships `gen_ai.*` spans straight to Dynatrace.

For a collector-based variant (which exports via OTLP and can redact secrets before they leave the host), see [`langgraph/opentelemetry`](../opentelemetry).

## What this sample does

- Runs a FastAPI server exposing `POST /haiku` (accepts a `{"topic": "..."}` body)
- Builds a minimal LangGraph state graph with a single `write_haiku` node that calls Azure OpenAI
- Relies on OneAgent to capture the agent's LLM calls as `gen_ai.*` spans
- Ships an OpenPipeline config (`openpipeline-langgraph.yaml`) that redacts captured messages mentioning secrets, server-side on ingest

## Redacting secrets with OpenPipeline

Because OneAgent sends spans directly to Dynatrace, there is no customer-side collector to filter in. The equivalent of the collector `transform` processor is a **server-side OpenPipeline** rule that runs on ingest.

`openpipeline-langgraph.yaml` replaces `gen_ai.input.messages` / `gen_ai.output.messages` / `gen_ai.system_instructions` with `***REDACTED***` whenever they contain the word `secret`. Deploy it under **Settings > OpenPipeline > Spans** and add a routing entry:

| Field | Value |
|-------|-------|
| Matcher | `dt.service.name == "langgraph/oneagent (langgraph-oneagent)" AND dt.openpipeline.source == "oneagent"` |
| Pipeline | `langgraph-redact-secrets` |

> **Trade-off vs. the collector approach:** OpenPipeline redacts *after* the data reaches Dynatrace, so the raw text travels from the host to the cluster before being masked. If secrets must never leave the host, use the collector-based [`langgraph/opentelemetry`](../opentelemetry) demo, which scrubs before egress.

### OpenPipeline implementation notes

When building OpenPipeline processors for OneAgent-captured `gen_ai.*` spans, keep these constraints in mind:

**Routing matcher** — use an exact `==` match on `dt.service.name` (the OneAgent display name, e.g. `"langgraph/oneagent (langgraph-oneagent)"`) rather than `matchesPhrase`. The display name differs from the OTLP `service.name` attribute and always includes the process group name in parentheses. Combining with `dt.openpipeline.source == "oneagent"` scopes the rule to OneAgent spans only.

**Processor matcher** — the matcher field supports a restricted DQL subset: `isNotNull()`, `isNull()`, equality operators (`==`, `!=`), and `AND`/`OR`/`NOT`. Functions like `matchesPhrase()`, `contains()`, and `matches()` are **not** available here for string content checks.

**DQL script** — the script field has a restricted command set: `filter` is not enabled and `contains()` cannot be used as a standalone filter. The correct pattern for conditional redaction is a `fieldsAdd` with an `if()` expression.

`gen_ai.input.messages` is stored as an **array type**, not a plain string, so `contains()` alone does not match against its content. Wrap it with `toString()` first to serialise the array to a string, then apply `contains()`:

```dql
fieldsAdd gen_ai.input.messages = if(contains(toString(gen_ai.input.messages), "secret"), "***REDACTED***", else: gen_ai.input.messages)
```

Note the required named `else:` parameter — a positional third argument is rejected. Also note that backtick-quoting field names (`` `gen_ai.input.messages` ``) is **not** valid DQL syntax here and will cause a parse error.

**`gen_ai.input.messages` format** — OneAgent serialises messages using a `parts` array rather than a flat `content` field:

```json
[{"parts":[{"type":"text","content":"Write a haiku about the secret launch codes."}],"role":"user"}]
```

This is why `contains()` on the raw field returns no results — the field is an array type. `toString()` serialises it to a plain string (without JSON quoting), making substring matching work reliably.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv`)
- Dynatrace OneAgent installed on the host
- An Azure OpenAI endpoint and key

## Environment

Copy `.env.sample` to `.env` and fill in the values:

```env
OPENAI_API_BASE=https://<resource>.openai.azure.com/openai/deployments/<deployment>
OPENAI_API_KEY=...
OPENAI_API_VERSION=2024-07-01-preview
MODEL=<deployment>
```

> The app also accepts `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` as alternatives — both naming conventions are supported.

## Install and run

```bash
cd langgraph/oneagent
make install
make run
```

Then in a second terminal:

```bash
make request         # non-secret topic — passes through
make request-secret  # secret topic — redacted once the pipeline is deployed
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Create venv and install dependencies via uv |
| `make run` | Start the FastAPI app on port 8000 |
| `make request` | POST /haiku with a non-secret topic |
| `make request-secret` | POST /haiku with a secret topic |
| `make request-all` | Exercise both paths |
| `make build` / `make push` | Build / push the container image |

## Dynatrace views

Open the **AI Observability** app and filter by `service.name = langgraph/oneagent` to explore the agentic trace, model, token usage, and latency. With the OpenPipeline deployed, secret-bearing messages show `***REDACTED***` while benign ones pass through.
