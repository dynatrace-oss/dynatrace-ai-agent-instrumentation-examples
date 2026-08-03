# Implementation plan — dt-evals fixtures (AI-298)

Derived from `dt-evals-fixtures/SPEC.md`. Work lives in
`dt-evals-fixtures/opentelemetry/`. One commit per task, each with a passing test.

## Tasks

1. **Deterministic multi-turn span emitter** ✅ *(done — commit aa8b19a)*
   - `FixtureModel` (FakeListChatModel + `llm_output` for model/usage),
     `tracing.py` (explicit LangChain instrumentation + conversation-id
     SpanProcessor + contextvar), `fixtures.py` (schema + normalize
     shorthand→turns, UUIDv5 conversation id), `ingest.py` (drive turns).
   - AC: given a 2-turn case, emits 2 spans sharing one `gen_ai.conversation.id`,
     each carrying `gen_ai.request.model` + `gen_ai.usage.*`; turn-2 span's
     `gen_ai.input.messages` holds the accumulated history. Verified with an
     in-memory exporter (no tenant).

2. **Wire `app.py` + `/ingest` to the new modules** ✅ *(done — commit 232398b)*
   — FastAPI app calls `init_tracing` from env, `/ingest` replays fixtures via
   `ingest.py`.

3. **Fixtures-well-formed validation test** ✅ *(done — commit b0e14eb)* — unique
   names, valid `targets` against the 14 evaluators, `expect` ∈ {pass,fail},
   required context/reference present where the evaluator needs it.

4. **`build_fixtures.py` — toxicity (hh-rlhf, real multi-turn)** ✅ *(done — commit a25b9d0)* — read from HF
   cache, curate a deterministic pass/fail subset, parse `Human:`/`Assistant:`
   into turns, write cases.

5. **`build_fixtures.py` — fluency (soda_eval, real multi-turn)** ✅ *(done — commit 6fd3a07)*

6. **`build_fixtures.py` — single-turn evaluators** wrapped as 1-turn
   conversations. ✅ *(done)* — QA-style (faithfulness, hallucination, relevance,
   factual-accuracy, answer-completeness) plus scaffolded evaluators where the
   dataset provides only one side (pii-leakage, summarization-quality,
   prompt-injection). Decision resolved: the non-evaluated half is a fixed
   scaffold (SPEC §3.7/§8).

7. **Download missing HF datasets** ✅ *(done)* — gooaq (context-relevance),
   daloopa (conciseness), IEMOCAP (user-frustration) downloaded; SBIC's HF loader
   is deprecated so StereoSet (cached) covers bias. All 14 evaluators covered.
   ⚠️ *Superseded by task 9:* gooaq, IEMOCAP and StereoSet were later dropped for
   licensing reasons (their evaluators are now self-authored).

8. **`SOURCES.md` + README + Makefile `build-fixtures` target** ✅ *(done)* —
   per-dataset attribution + licensing note.

9. **Licensing rework for public OSS** ✅ *(done, 2026-08-03)* — repo is public
   Apache-2.0, so 5 evaluators whose source datasets are not redistributable
   (IEMOCAP, StereoSet, Magneto, gooaq, FaithEval) were switched to self-authored
   content; the other 9 keep MIT/Apache/CC-BY datasets with explicit attribution.
   See SPEC §3.7 / §9.8.

**Status: all tasks complete. fixtures.json = 28 cases across all 14 dt-evals
judge evaluators (2 pass/fail each) — 9 from permissive datasets, 5 self-authored.
35 tests passing.**
