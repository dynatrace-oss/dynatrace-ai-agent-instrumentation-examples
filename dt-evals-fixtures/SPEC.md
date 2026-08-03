# SPEC — dt-evals deterministic fixtures (AI-298)

> Spec-driven definition of the `dt-evals-fixtures` work. Scope is the
> `dt-evals-fixtures/` subtree of `dynatrace-ai-agent-instrumentation-examples`.
> Status: draft for review.

## 1. Objective

Provide a **deterministic, representative GenAI-span dataset** that the
[`dt-evals`](https://github.com/dynatrace-oss/dt-evals) project can use as a
stable end-to-end regression baseline.

The problem: every other example in this repo runs a real framework against a
real LLM, so the emitted spans — and any eval score derived from them — differ
from run to run. A regression suite needs the opposite: **the same prompt and
the same answer every time**, so a toxic answer always scores toxic and a clean
one always passes.

The approach (already prototyped): drive a real, Traceloop-instrumented
LangChain chat model where the model is a `FakeListChatModel` pre-programmed
with canned answers from `fixtures.json`. The spans travel the same
instrumentation path a real LangChain app uses, so they carry exactly the
`gen_ai.*` attribute shape `dt-evals` reads in production via `fetch spans` — no
hand-built spans, no LLM provider, no collector, no API key.

**Primary consumer:** the `dt-evals` **CI / e2e test suite**, which fetches
these spans from a Dynatrace tenant, scores them with a judge LLM, and asserts
the scores are stable across runs.

**Success looks like:**

- `dt-evals` e2e tests can point at `service.name = dt-evals-fixtures` and get
  identical scores on every run.
- Every supported evaluator has **2 multi-turn conversations** — one that
  clearly *passes* and one that clearly *fails/violates* — so both directions of
  the score are asserted. Single-turn coverage is subsumed by multi-turn.
- Emitted spans carry the attributes each targeted evaluator needs (input,
  output, and where required: context, reference answer, token usage, model
  name).
- The dataset includes **real multi-turn conversations** — one span per turn,
  linked by a shared `gen_ai.conversation.id` — mirroring how production
  chatbots emit spans in the wild (see §3.5).
- All example content is **sourced from real evaluation datasets** (NVIDIA
  Nemotron-PII / HelpSteer2, Anthropic hh-rlhf, ToxiGen, TruthfulQA, …), never
  hand-generated (see §3.7).

## 2. Non-goals

- Not a benchmark of eval *accuracy* — we assert score *stability*, not that the
  judge is "right".
- No real LLM calls, no collector, no container/Dockerfile (the `build`/`push`
  Makefile targets are intentional no-ops).
- `drift` (7-day statistical baseline) is **out of scope** for a single e2e run;
  note it, don't try to make it deterministic here.

## 3. Dataset design (the core of this work)

### 3.1 Target evaluators

`dt-evals` ships 14 judge-based evaluators (plus statistical `drift`). The
dataset should cover the judge-based ones:

| Evaluator | Measures | Needs beyond input/output |
|-----------|----------|---------------------------|
| `toxicity` | harmful/offensive output | — |
| `faithfulness` | output grounded in context | **context** |
| `hallucination` | unsupported/fabricated claims | **context** |
| `relevance` | output addresses the request | — |
| `user-frustration` | frustration in the user input | (evaluates input) |
| `fluency` | grammar/clarity | — |
| `factual-accuracy` | accuracy vs a reference | **reference answer** |
| `answer-completeness` | all parts answered | — |
| `context-relevance` | retrieval quality of context | **context** |
| `pii-leakage` | PII in output | — |
| `prompt-injection` | injection in the input | (evaluates input) |
| `bias` | harmful bias / unfair framing | — |
| `summarization-quality` | summary faithfulness/coverage | **source text** |
| `conciseness` | avoids filler/padding | — |

### 3.2 Fixture schema (needs extending)

The current `fixtures.json` case is `{name, system, user, response}`. To cover
the evaluators above **and** multi-turn (§3.5), unify every case around an
ordered `turns` list — one entry per conversation turn. A single-turn case is
just one turn; `system`/`user`/`response` stay accepted as shorthand and are
normalized internally to `turns: [{user, response}]`.

```jsonc
{
  "name": "faithful-grounded",         // unique, kebab-case
  "targets": ["faithfulness"],          // which evaluator(s) this case exercises
  "expect": "pass",                     // "pass" | "fail" — asserted direction (case-level default)
  "system": "…",                        // system prompt, shared across all turns
  "context": "…",                       // optional: for faithfulness/hallucination/context-relevance
  "reference": "…",                     // optional: for factual-accuracy
  "usage": { "input_tokens": 12, "output_tokens": 8 },  // optional, per emitted span
  "model": "gpt-4.1",                   // optional: sets gen_ai.request.model
  "turns": [
    { "user": "…", "response": "…" }    // each turn → exactly one emitted span
    // add more turns for multi-turn; "expect"/"targets" may be set per turn
  ]
}
```

`targets` + `expect` make the dataset self-documenting and let the e2e test run
only the relevant metric per case (see cost trade-off below). For multi-turn
cases these may be set on the individual turn that carries the asserted
behaviour (e.g. the final, frustrated turn).

### 3.3 Coverage & cost trade-off

**Everything is multi-turn.** A multi-turn conversation subsumes the single-turn
case: every turn emits its own span that is, on its own, a single-turn-shaped
evaluation input, and the final turn is the classic single-turn evaluation. So
there are no separate single-turn cases — single-turn coverage falls out of the
multi-turn conversations for free.

Target: **2 multi-turn conversations per evaluator** — one that clearly `pass`es
and one that clearly `fail`s — across all 14 judge-based evaluators, i.e.
**~28 conversations**. Each conversation carries the asserted behaviour on the
turn where it manifests (via per-turn `expect` / `targets`).

Cost constraint: the fixtures emit no LLM calls themselves, but each conversation
costs judge-LLM calls in the e2e pipeline (roughly one per evaluated turn-span
for its `targets` metric). The `targets` field lets the e2e suite run metric *X*
only against the conversations tagged for *X*, keeping judge calls proportional
to the tagged spans rather than `spans × metrics`.

> OPEN DECISION: how many turns per conversation (drives total span count and
> judge cost). Keep conversations short (≈2–4 turns) unless a metric needs a
> longer build-up. Revisit once we see real e2e runtime + cost.

### 3.4 Solving the fake-model caveats

`FakeListChatModel` reports no real token usage and no real model name, so
`gen_ai.usage.*` and `gen_ai.request.model` land as empty/`"unknown"`. Decision:
**make these settable per fixture** (`usage`, `model` fields) via a small
`FakeListChatModel` subclass.

**Verified mechanism** (see §3.6): the instrumentation reads the model name and
token usage from the `ChatResult.llm_output` dict on `on_llm_end`
(`callback_handler.py` ~740/764). A subclass that overrides `_generate` to set
`llm_output = {"model_name": <model>, "token_usage": {"prompt_tokens": …,
"completion_tokens": …, "total_tokens": …}}` makes the instrumentation stamp
`gen_ai.request.model`, `gen_ai.response.model`, and `gen_ai.usage.*` correctly.
A span-processor approach does **not** work for the model name — the
instrumentation overwrites it with `"unknown"` on `on_llm_end`.

### 3.5 Multi-turn conversations (real spans, not inlined history)

Requirement: the dataset must contain **real multi-turn conversations as they
occur at companies** — i.e. **one span per turn**, linked by a shared
conversation id — not a single span with the whole history inlined. (`dt-evals`
does not group multi-span conversations *yet*; that support is being built now,
and this dataset is the fixture it will be validated against.)

**How the spans are produced** (fits the existing architecture):

- Each case with N turns triggers **N sequential `model.invoke()` calls** — one
  per turn — so N spans are emitted.
- Every turn N resends the **accumulated history** as input: `system` + all
  prior `(user, assistant)` pairs + the current `user` message. This mirrors a
  production chatbot resending context on every request.
- All N spans of a conversation carry the **same `gen_ai.conversation.id`**
  (the OTel GenAI semconv attribute). See §3.6 for how it is set — the native
  LangGraph `thread_id` path does **not** apply to plain `model.invoke()`.
- Each turn is its **own root span / trace** (separate invoke, no parent),
  linked only by `gen_ai.conversation.id` — like the separate HTTP requests a
  real chat backend receives. (Verified: turn-2's span carries the full history
  `['user','assistant','user']` in `gen_ai.input.messages`; the system prompt is
  emitted separately as `gen_ai.system_instructions`, per the new semconv.)
- `FakeListChatModel` returns each turn's canned `response` in order, keeping
  every turn deterministic.

**Conversation id:** a **UUIDv5 derived from the case `name`** — stable across
runs (so the e2e suite can assert on it) and shaped like a real production id.

**Dependency on the `dt-evals` side (in-progress work):** the DQL fetch
currently selects `trace.id` but **not** `gen_ai.conversation.id`
(`dt-eval-cli/src/dt/dql.ts`). The multi-span implementation must (a) select
`gen_ai.conversation.id` and (b) group/order spans by it (turn order via
span start time). Tracked as a cross-repo dependency, not owned here.

### 3.6 Verified instrumentation mechanics (langchain-core 1.5.3, traceloop-sdk 0.62.1)

Confirmed empirically against the pinned deps (in-memory exporter, no tenant).
These override two assumptions earlier drafts made:

1. **Explicit instrumentation required.** `Traceloop.init()` does **not**
   auto-instrument LangChain when only `langchain-core` is installed (the
   meta-package `langchain` is absent). `FakeListChatModel.invoke()` fires
   callbacks but emits **zero spans** until the app calls
   `LangchainInstrumentor().instrument()` explicitly. → the app must do this
   (or add the `langchain` package). Without it, the current `app.py` emits
   nothing.

2. **Conversation id is set by us, not by `thread_id`.** The native
   `config.configurable.thread_id → gen_ai.conversation.id` mapping lives in the
   LangGraph `on_chain` path (it also checks `langgraph_node`); it does **not**
   fire for a plain chat-model `invoke()`. Passing `thread_id` leaves
   `gen_ai.conversation.id` unset. → set it ourselves with a small
   `SpanProcessor.on_start` that stamps `gen_ai.conversation.id` from a
   `contextvar` set around each turn's `invoke()`. Verified: both turns of a
   conversation share the id, each in its own trace.

3. **Model / usage** flow through the `FixtureModel` subclass (§3.4), not a span
   processor.

The end-to-end recipe (instrument explicitly → add the conv-id SpanProcessor →
`FixtureModel` with `llm_output` → drive turns with the contextvar set) is
proven to emit complete, deterministic multi-turn GenAI spans.

### 3.7 Data sourcing — real datasets only (never hand-generated)

**Principle:** every fixture's prompt/response content is drawn from a real,
established evaluation dataset — not authored by us. This gives the spans
realistic, representative content and a defensible ground-truth label. The
source datasets are the ones already curated by the sibling repo
[`aiobs-eval-promptlib`](../../aiobs-eval-promptlib) (see its `DATASETS.md`),
most of which are already present locally in the HuggingFace cache
(`~/.cache/huggingface/datasets/`).

**Evaluator → source dataset** (aligned to the 14 dt-evals evaluators; ✅ = in
local HF cache):

| Evaluator | Source dataset | Multi-turn? | GT → `expect` |
|-----------|----------------|-------------|---------------|
| toxicity | `Anthropic/hh-rlhf` harmless-base ✅ | **real multi-turn** | `chosen`→pass, `rejected`→fail |
| fluency | `Johndfm/soda_eval` ✅ | **real multi-turn** | fluent→pass, issue→fail |
| pii-leakage | `nvidia/Nemotron-PII` ✅ | single | `has_pii`→fail else pass |
| faithfulness | `Salesforce/FaithEval-counterfactual` ✅ | single | MCQ answerKey match |
| hallucination | `Cleanlab/FinQA-hallucination` ✅ | single | `is_hallucination`→fail |
| relevance | `nvidia/HelpSteer2` (helpfulness) / RAGBench ✅ | single | rating/label threshold |
| factual-accuracy | `domenicrosati/TruthfulQA` ✅ | single | best→pass, incorrect→fail |
| answer-completeness | `Magneto/qa-dataset-llm-judge` ✅ | single | `score`≥0.5→pass |
| prompt-injection | `neuralchemy/Prompt-injection` ✅ | single | `label==1`→fail |
| summarization-quality | `abisee/cnn_dailymail` ✅ | single | reference→pass |
| context-relevance | `zilliz/gooaq-context-relevance` ⬇ | single | `context_relevance`≥0.5→pass |
| bias | Social Bias Frames (SBIC) ⬇ | single | `bias`→fail |
| conciseness | `daloopa/financial-retrieval` ⬇ | single | length-proxy |
| user-frustration | `AbstractTTS/IEMOCAP` ⬇ (gated) | single | `frustrated`≥0.5→fail |

⬇ = **not in local cache, must be downloaded from HF** (per the resolved
decision). IEMOCAP is gated → needs an HF token.

**Multi-turn handling** (per §3.3 / resolved decision): genuine multi-turn spans
come from the two datasets that actually carry conversations — `hh-rlhf`
(toxicity) and `soda_eval` (fluency). For every other evaluator, a real
single-turn row is embedded as a **1-turn conversation** (one span, same
`gen_ai.conversation.id` mechanics). So the content is 100% real everywhere;
multi-turn is genuine only where the source provides it — we never fabricate a
conversation flow.

**Grounding context / reference attributes** (verified against a real tenant):
the fixture `context` and `reference` do not map to any standard OTel GenAI
attribute, and the native instrumentation emits neither. They are stamped onto
the spans as custom attributes `gen_ai.context` / `gen_ai.reference` (via the
same SpanProcessor path as the conversation id). Because dt-evals ships no
default context field, its config **must** map `spanFields.context:
gen_ai.context` to consume them — a cross-repo contract recorded in
`opentelemetry/SOURCES.md`.

**Scaffolding the missing half of a turn** (resolved decision): some evaluators
score only one side of a turn, and their source dataset provides only that side —
input-scoring evaluators (`prompt-injection`, `user-frustration`) give only the
user input; text-only datasets (`pii-leakage`, `summarization-quality`, `bias`)
give only the text to judge, with no user prompt. A GenAI chat span needs both
sides. Rule: **the evaluated half is always real dataset content; the
non-evaluated half is a fixed, generic scaffold string** (e.g. `user:
"Summarize the following article."` for summarization, or `assistant: "Sure, I
can help with that."` for prompt-injection). Scaffolds are fixed (deterministic)
and recorded as `"scaffold": true` in the case `source` so provenance stays
honest. This is the one sanctioned exception to "never hand-author" (§8).

**Conversion step:** a small script reads the chosen rows from the cache / HF,
**curates a deterministic subset** (hand-pick clear pass/fail exemplars — e.g.
`hh-rlhf` row 0 is not a clean "pass"), parses them into the `turns` schema
(`hh-rlhf` splits on `Human:` / `Assistant:` markers), tags `targets` / `expect`
from the dataset's GT rule above, and writes `fixtures.json`. Reuse
`aiobs-eval-promptlib`'s existing dataset loaders where practical.

**Attribution / licensing:** because real dataset excerpts are committed into
this repo, record each source dataset + its license/attribution (e.g. in the
README or a `SOURCES.md`). Check per-dataset license terms before committing
excerpts. `OPEN`: confirm all chosen datasets permit redistribution of small
excerpts.

## 4. Commands

Run from `dt-evals-fixtures/opentelemetry/`:

| Command | Does |
|---------|------|
| `make install` | `uv sync` — install deps |
| `make run` | start the FastAPI app on `$PORT` (default 8000) |
| `make request` | `POST /ingest` — replay every fixture as a GenAI span |
| `make help` | list targets |
| `make build` / `make push` | intentional no-ops (no container) |

Env (via `.env`, see `.env.sample`): `DT_ENDPOINT`, `DT_API_TOKEN`, optional
`PORT`.

## 5. Project structure

```
dt-evals-fixtures/
├── SPEC.md                     # this file
└── opentelemetry/
    ├── app.py                  # FastAPI app; Traceloop init; /ingest replays fixtures
    ├── build_fixtures.py       # sources real dataset rows → curated fixtures.json (§3.7)
    ├── fixtures.json           # the dataset (cases + service_name), generated by build_fixtures
    ├── SOURCES.md              # per-dataset attribution + license (§3.7)
    ├── pyproject.toml          # deps: langchain-core, traceloop-sdk, fastapi, uvicorn (+ datasets for build)
    ├── uv.lock                 # pinned lockfile (commit it)
    ├── Makefile                # install / run / request / build-fixtures / help
    ├── .env.sample             # DT_ENDPOINT + DT_API_TOKEN template
    └── README.md               # how to run + fixture format
```

## 6. Code style

- Python ≥3.10, managed with `uv`; deps pinned in `uv.lock`.
- Match the existing `app.py`: module docstring explaining *why*, env vars set
  before importing instrumented libs, small focused functions with docstrings.
- Fixtures are data, not code — no logic in `fixtures.json`; anything dynamic
  (token usage, model name) is driven by explicit fixture fields.
- Keep the app dependency-light: no collector, no extra frameworks beyond what's
  in `pyproject.toml`.
- Call `LangchainInstrumentor().instrument()` explicitly at startup (§3.6) —
  auto-instrumentation does not fire with only `langchain-core`. Guard with
  `is_instrumented_by_opentelemetry` to avoid double-instrumenting.

## 7. Testing strategy

- **Owned here:** a smoke path — `make run` + `make request` returns
  `{"ingested": N, "cases": [...]}` with no errors, and spans arrive under
  `service.name = dt-evals-fixtures` on the tenant.
- **Optional guard:** a small local test asserting `fixtures.json` is
  well-formed — unique `name`s, valid `targets` against the known evaluator
  list, `expect` ∈ {`pass`,`fail`}, and required extra fields present for
  evaluators that need them (e.g. `context` for `faithfulness`).
- **Consumed by:** `dt-evals` e2e tests (in the `dt-evals` repo) assert score
  stability against this dataset. That assertion lives there, not here.

## 8. Boundaries

**Always**

- Keep every emitted span deterministic — fixed input *and* fixed output.
- Emit through the real instrumentation path (Traceloop/LangChain), never
  hand-build spans.
- Keep `fixtures.json` self-documenting via `name` / `targets` / `expect`.
- Emit multi-turn as **one span per turn** sharing a stable
  `gen_ai.conversation.id`; never inline the whole conversation into one span.
- Source all example content from real datasets (§3.7); record each source's
  attribution/license.

**Ask first**

- Before adding a real LLM provider, a collector, or a container.
- Before growing the dataset well beyond the ~25–30 case budget (judge-call
  cost).
- Before changing `service.name` (e2e tests filter on it).

**Never**

- Never commit real secrets — `.env` stays local, only `.env.sample` is tracked.
- Never introduce run-to-run variability (random values, timestamps in content,
  real model output).
- Never target `drift` for deterministic assertion.
- Never hand-author the **evaluated** half of a turn — it must come from a real
  dataset (§3.7). The one exception: the **non-evaluated** half may be a fixed
  generic scaffold when the source dataset provides only one side, marked
  `"scaffold": true` in the case source.
- Never fabricate a multi-turn flow — multi-turn only where the source dataset
  genuinely provides conversations.

## 9. Decisions (resolved)

1. **Coverage:** 2 multi-turn conversations per evaluator (one `pass`, one
   `fail`), all 14 judge-based evaluators, ~28 conversations. No separate
   single-turn cases — subsumed by multi-turn. (§3.3)
2. **No borderline conversation** for now — pass/fail only; judges are flaky at
   the edge, which would undercut determinism. Revisit later. (§3.3)
3. **Turns per conversation:** variable, ~2–4 — only as long as the metric needs.
   Tune against real e2e cost. (§3.3)
4. **Conversation id:** UUIDv5 derived from the case `name`. (§3.5)
5. **Long-term home:** stays here in this examples repo; `dt-evals` fetches
   spans from the tenant at runtime — coupling is only the `service.name`
   contract, no vendoring. (§2)
6. **Instrumentation & attributes:** verified empirically — see §3.6. Explicit
   `LangchainInstrumentor().instrument()`, conv-id via `SpanProcessor` +
   contextvar, model/usage via `FixtureModel` subclass. (Supersedes the old
   `thread_id` assumption.)
7. **Data sourcing:** all content from real datasets, never generated (§3.7).
   Genuine multi-turn from `hh-rlhf` (toxicity) + `soda_eval` (fluency); every
   other evaluator uses a real single-turn row wrapped as a 1-turn conversation.
8. **Missing datasets** (gooaq, SBIC, daloopa, IEMOCAP) are **downloaded from
   HF** (IEMOCAP is gated → needs an HF token). (§3.7)

### Still open

- Whether to add the fixtures-well-formed validation test (§7) now or later —
  recommendation: add a lightweight version alongside the dataset.
- Confirm each source dataset's license permits committing small excerpts into
  this repo (§3.7 attribution/licensing).
