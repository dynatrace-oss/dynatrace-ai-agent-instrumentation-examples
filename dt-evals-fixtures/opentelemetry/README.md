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
key. See [`../SPEC.md`](../SPEC.md) for the full design.

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
  "model": "gpt-4.1",                     // optional: sets gen_ai.request.model
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

### Content is sourced, not generated

The example content is **not** hand-written — it is drawn from established
evaluation datasets (NVIDIA Nemotron-PII / HelpSteer2, Anthropic HH-RLHF,
ToxiGen, TruthfulQA, StereoSet, …). See [`SOURCES.md`](SOURCES.md) for the full
per-evaluator mapping and attribution.

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
produces linked multi-turn spans with the right attributes, that every builder
maps its dataset correctly, and that the shipped `fixtures.json` is well-formed.
