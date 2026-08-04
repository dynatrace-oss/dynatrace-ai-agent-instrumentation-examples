# dt-evals fixtures (OpenTelemetry)

Deterministic GenAI spans for dt-evals end-to-end tests.

Every other example in this repo runs a real framework against a real LLM, so
the spans — and any eval score derived from them — differ from run to run. An
eval regression suite needs the opposite: **the same prompt and the same answer
every time**, so a toxic answer always scores toxic and a clean one always
passes.

This example drives a real, Traceloop-instrumented LangChain chat model, but the
model is a `FixtureModel` (a [`FakeListChatModel`](https://reference.langchain.com/python/langchain-core/language_models/fake_chat_models/FakeListChatModel)
with a fixed model name + token usage) pre-programmed with the answers in
`fixtures.json`. Because the spans come from the same instrumentation path a real
LangChain app uses, they carry exactly the `gen_ai.*` attribute shape dt-evals
sees in production — no hand-built spans, no LLM provider, no collector, no API
key.

## Run

```bash
cp .env.sample .env   # fill in DT_ENDPOINT + DT_API_TOKEN
make install
make run               # in one shell
make request           # in another — POSTs /ingest, replays every fixture
```

The spans land under `service.name = dt-evals-fixtures` (the `service_name`
field in `fixtures.json`).

## Fixtures

`fixtures.json` holds a list of `cases`. Each case is an ordered list of `turns`
(one emitted span per turn):

```jsonc
{
  "name": "toxicity-hhrlhf-1065-fail",  // unique
  "system": "You are a helpful assistant.",
  "targets": ["toxicity"],               // which dt-evals evaluator(s) it exercises
  "expect": "fail",                       // asserted direction: "pass" | "fail"
  "context": "…",                         // optional: for faithfulness/hallucination/…
  "reference": "…",                       // optional: for factual-accuracy
  "model": "gpt-4o-mini",                 // optional: sets gen_ai.request.model
  "usage": {"input_tokens": 12, "output_tokens": 8},  // optional
  "turns": [
    {"user": "…", "response": "…"},       // each turn -> one span
    {"user": "…", "response": "…", "expect": "fail", "targets": ["toxicity"]}
  ],
  "source": {"dataset": "…", "row": 1065} // provenance
}
```

A single-turn case may use the `system`/`user`/`response` shorthand instead of
`turns`.

### Multi-turn

Multi-turn conversations are emitted as **one span per turn**, all sharing a
`gen_ai.conversation.id` (a stable UUIDv5 of the case name) — the same shape a
production chatbot produces. Genuine multi-turn cases come from datasets that
carry real conversations (toxicity, fluency); other evaluators use a real
single-turn row as a one-turn conversation.

### Content sources

Most content is drawn from established evaluation datasets whose license permits
redistribution (NVIDIA Nemotron-PII / HelpSteer2, Anthropic HH-RLHF, TruthfulQA,
SummEval, …). Five evaluators (faithfulness, answer-completeness,
context-relevance, bias, user-frustration) use short **self-authored** content
instead, because their natural source datasets were not permissively licensed for
a public repo. See [`SOURCES.md`](SOURCES.md) for the full per-evaluator mapping,
licenses, and attribution.

> **Content warning.** Some fixtures deliberately contain toxic, biased, or
> PII-shaped text — they are the negative test inputs for the toxicity, bias, and
> pii-leakage evaluators. Any PII is synthetic; none of it is real personal data.

### Dataset budget

The dataset is deliberately small: **two conversations per evaluator**, one that
clearly passes and one that clearly fails, across all 14 judge-based evaluators.
That comes to 28 conversations of roughly 2–4 turns each.

The size is a cost decision, not an oversight. These fixtures make no LLM calls
themselves, but every conversation costs judge-LLM calls once dt-evals scores it.
That is what `targets` is for: the e2e suite runs evaluator *X* only against the
conversations tagged for *X*, so judge calls stay proportional to tagged spans
instead of `spans × evaluators`.

Two rules follow from that:

- **Ask before growing much past ~30 cases.** The judge bill scales with it.
- **No borderline cases.** Only clear passes and clear fails. Judges are flaky
  near the decision boundary, which would undercut the determinism this dataset
  exists to provide.

## Consuming these fixtures in dt-evals

Two contracts matter on the dt-evals side.

**`service.name`.** dt-evals fetches these spans from the tenant by filtering on
`service.name = dt-evals-fixtures`. That value comes from the `service_name`
field in `fixtures.json` (Traceloop's `app_name`), *not* from the
`OTEL_SERVICE_NAME` env var. Changing it breaks the e2e DQL filter and the metric
lookup, so treat it as a fixed contract.

**`gen_ai.conversation.id`.** Multi-turn grouping needs this attribute, and the
DQL fetch in dt-evals (`dt-eval-cli/src/dt/dql.ts`) historically selected
`trace.id` without it. Each turn here is its own root span in its own trace, so a
consumer that only reads `trace.id` sees 28 conversations that never group. To
group them, select `gen_ai.conversation.id` and order turns by span start time.
This is a cross-repo dependency, tracked in dt-evals rather than owned here.

## Regenerating fixtures

`fixtures.json` is committed, so running the app never needs the datasets. To
rebuild it from the source datasets (a dev task):

```bash
make build-fixtures    # runs build_fixtures.py; needs the HF datasets cached
```

`build_fixtures.py` reads the source rows from the local HuggingFace cache,
curates a deterministic pass/fail pair per evaluator, and writes `fixtures.json`.
The `datasets` library is a dev-only dependency.

## Tests

```bash
make test              # or: uv run pytest -q
```

Tests use an in-memory span exporter (no tenant): they verify the emitter
produces linked multi-turn spans with the right attributes, that each builder
produces well-formed pass/fail cases, and that the shipped `fixtures.json` is
well-formed.
