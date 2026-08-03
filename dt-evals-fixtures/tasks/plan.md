# Implementation plan — dt-evals fixtures (AI-298)

Derived from `dt-evals-fixtures/SPEC.md`. Work lives in
`dt-evals-fixtures/opentelemetry/`. One commit per task, each with a passing test.

## Tasks

1. **Deterministic multi-turn span emitter** *(this task)*
   - `FixtureModel` (FakeListChatModel + `llm_output` for model/usage),
     `tracing.py` (explicit LangChain instrumentation + conversation-id
     SpanProcessor + contextvar), `fixtures.py` (schema + normalize
     shorthand→turns, UUIDv5 conversation id), `ingest.py` (drive turns).
   - AC: given a 2-turn case, emits 2 spans sharing one `gen_ai.conversation.id`,
     each carrying `gen_ai.request.model` + `gen_ai.usage.*`; turn-2 span's
     `gen_ai.input.messages` holds the accumulated history. Verified with an
     in-memory exporter (no tenant).

2. **Wire `app.py` + `/ingest` to the new modules** — FastAPI app calls
   `init_tracing` from env, `/ingest` replays fixtures via `ingest.py`.

3. **Fixtures-well-formed validation test** — unique names, valid `targets`
   against the 14 evaluators, `expect` ∈ {pass,fail}, required context/reference
   present where the evaluator needs it.

4. **`build_fixtures.py` — toxicity (hh-rlhf, real multi-turn)** — read from HF
   cache, curate a deterministic pass/fail subset, parse `Human:`/`Assistant:`
   into turns, write cases.

5. **`build_fixtures.py` — fluency (soda_eval, real multi-turn)**.

6. **`build_fixtures.py` — single-turn evaluators** wrapped as 1-turn
   conversations (Nemotron-PII, FaithEval, FinQA, HelpSteer2, TruthfulQA,
   Magneto, neuralchemy, cnn_dailymail).

7. **Download missing HF datasets** (gooaq, SBIC, daloopa, IEMOCAP-gated) and
   add their evaluators.

8. **`SOURCES.md` + README + Makefile `build-fixtures` target**; per-dataset
   attribution/license.
