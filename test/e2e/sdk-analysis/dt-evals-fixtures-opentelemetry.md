# dt-evals Fixtures + FastAPI — Baseline Analysis

> **Baseline**: sdk-comparison-baseline.json v1.3.0 | **Path**: `dt-evals-fixtures/opentelemetry/` (`app.py` + `tracing.py` + `ingest.py` + `fixture_model.py`) | **Profile**: generic | **Dashboard**: `abmodelversioning.dashboard.json`

## Instrumentation

- **Library**: `traceloop-sdk==0.62.1` + `opentelemetry-instrumentation-langchain==0.62.1` over `langchain-core`. **Not a real LLM app** — it is a deterministic fixture replayer. `ingest.py` drives a `FixtureModel` (a `FakeListChatModel` subclass) with canned answers from `fixtures.json`; every run emits byte-identical GenAI spans, so an eval regression suite can assert against them.
- **Provider**: None — there is no inference vendor. The model is fake. The LangChain instrumentation's `detect_vendor_from_class("FixtureModel")` matches no rule and falls back to the framework default, so the chat span carries `gen_ai.provider.name = "langchain"` (see "Provider identity" below). No bare `gen_ai.system` is emitted at this version.
- **OTel setup**: `tracing.py` sets `TRACELOOP_TRACE_CONTENT=true` (the real content-capture gate for this instrumentor) and `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`, then calls `Traceloop.init(app_name="dt-evals-fixtures", disable_batch=True, should_enrich_metrics=True, api_endpoint=DT_ENDPOINT/api/v2/otlp, headers={Authorization: Api-Token …})` and explicitly `LangchainInstrumentor().instrument()` (required — Traceloop does not auto-instrument `langchain-core` alone). **Export is direct OTLP to the Dynatrace tenant — there is no collector.** A custom `FixtureSpanProcessor` stamps `gen_ai.conversation.id`, `gen_ai.context`, and `gen_ai.reference` from a contextvar onto every span of a case.
- **Synthetic model & usage**: `FixtureModel` populates `ChatResult.llm_output = {"model_name": "gpt-4o-mini", "token_usage": {...}}`. These are real span *attributes* on a real instrumentation path, but the model is a fixed default and usage is a deterministic content-derived estimate (~4 chars/token) — **not** a real inference.

## Verdict: PASS

Span audit against the generic profile: all required attributes pass with **native (non-fallback)** modern attributes. Not `FULL` only because a few optional attributes are absent (AR-009, AR-010, AR-024, AR-042). The e2e test (`dt_evals_fixtures_opentelemetry_test.go`) uses `auditSpanWithMetrics` and **asserts** the two GenAI client metrics (AR-025/AR-044) reach the tenant — so a green run confirms metric delivery over direct OTLP (no collector). The metric-backed rows below are marked ⚠️ until that first green run lands; flip them to ✅ once confirmed.

| Check | Rule | Status | Detail |
|-------|------|--------|--------|
| Provider identity (`must_have_any`) | AR-001/AR-002 | ✅ present, but framework value | `gen_ai.provider.name = "langchain"` (vendor detection default for a fake model); gate passes on presence, but this is the *framework*, not an inference vendor. No `gen_ai.system`. |
| `service.name` | AR-003 | ✅ | `"dt-evals-fixtures"` from Traceloop `app_name` (the `service_name` field in `fixtures.json`) |
| `gen_ai.request.model` | AR-004 | ✅ synthetic | `"gpt-4o-mini"` from `FixtureModel.llm_output.model_name` (fixed, not a real request) |
| `gen_ai.response.model` | AR-005 | ✅ synthetic | same `"gpt-4o-mini"` — set from the same `llm_output` on `on_llm_end` |
| `gen_ai.usage.input_tokens` | AR-006 | ✅ **native** | Modern attribute name emitted directly (not the deprecated `prompt_tokens` fallback the siblings use). Value is a synthetic estimate. |
| `gen_ai.usage.output_tokens` | AR-007 | ✅ **native** | Modern attribute name emitted directly (not `completion_tokens`). Value is a synthetic estimate. |

## App view coverage

| View | Status | Root cause |
|------|--------|------------|
| All GenAI views gate | ✅ | Provider identity + all required fields present natively |
| Prompts — content | ✅ **modern** | Emits `gen_ai.input.messages` / `gen_ai.output.messages` (AR-011/AR-012) natively at v0.62.1 — not the legacy `gen_ai.prompt.*`/`completion.*` the siblings fall back to. Gated by content capture (`should_send_prompts()` default true). |
| Prompts — model column | ✅ | `gen_ai.request.model` present |
| Latency charts | ⚠️ unverified | Instrumentation *does* record the `gen_ai.client.operation.duration` histogram (AR-025), and the app sets `should_enrich_metrics=True` + delta temporality. But metric delivery goes direct OTLP to the tenant with **no collector**, and the e2e suite does not assert it — see "Metrics without a collector" below. |
| Cost dashboard (span tokens) | ✅ | `gen_ai.usage.input_tokens`/`output_tokens` present on spans (AR-006/AR-007, native) — synthetic values |
| Cost dashboard (metric) | ⚠️ unverified | Instrumentation records the `gen_ai.client.token.usage` histogram (AR-044); same direct-OTLP/no-collector uncertainty as latency |
| Service health tile | ✅ | `span.status_code` (AR-047) auto-emitted by the OTel SDK |
| Agent quick filter | ❌ | No `gen_ai.agent.name` (AR-010) — this is a plain `model.invoke()`, not an agent/graph run; the instrumentor's agent wrapper never fires |
| Provider quick filter | ⚠️ | Populated, but every span reads `"langchain"` — the framework, not a real provider |
| Guardrails (Azure/Bedrock) | N/A | Generic profile; no guardrail data |
| Cache hit rate (OpenAI) | N/A | Not applicable for generic profile; no real provider |

## Dashboard Coverage

| Dashboard View | Populated? | Missing / caveat |
|----------------|------------|------------------|
| All GenAI spans | ✅ Yes | — |
| Prompts list / detail | ✅ Yes (modern) | `gen_ai.input.messages` / `gen_ai.output.messages` present natively — no legacy fallback needed |
| Latency charts (p99/mean) | ⚠️ Unverified | `gen_ai.client.operation.duration` (AR-025) is recorded by the instrumentor; delivery via direct OTLP metrics (no collector) is not asserted by the suite |
| Cost dashboard tiles | ⚠️ Unverified | `gen_ai.client.token.usage` (AR-044) recorded; same delivery uncertainty. Span-level token attributes (AR-006/007) are present regardless. |
| Service health tile | ✅ Yes | `span.status_code` auto-emitted by OTel SDK |
| Agent quick filter | ❌ Empty | `gen_ai.agent.name` (AR-010) not emitted for a plain chat invoke |
| Audit trail | ❌ Not applicable | No `gen_ai.auditing` bizevents emitted |
| Evaluation results | ❌ Not applicable | dt-evals scores these spans downstream; the app itself emits no evaluation bizevents |

## Silent failures

Attributes/metrics absent (or whose delivery is unverified) that cause empty charts with no visible error:

| Attribute / Metric | Rule ID | Missing feature |
|--------------------|---------|-----------------|
| `gen_ai.client.operation.duration` (metric) | AR-025 | Latency charts empty **if** direct-OTLP metric delivery to the tenant fails (no collector; not asserted by the suite) |
| `gen_ai.client.token.usage` (metric) | AR-044 | Cost metric tiles empty under the same condition; distinct from span token attrs AR-006/AR-007 which are present |
| `gen_ai.token.type` (metric dimension) | AR-024 | Cost dashboard breakdown by input/output has no dimension on spans; carried on the metric if the metric arrives |
| `gen_ai.agent.name` | AR-010 | Agent quick filter empty — not applicable to a plain chat invoke |
| `llm.request.type` | AR-009 | Not emitted at this instrumentation version (optional Traceloop legacy attr) |
| `gen_ai.request.temperature` | AR-042 | Absent — `FakeListChatModel` exposes no `temperature` in `invocation_params` |
| provider value | AR-001/AR-002 | Present but reads `"langchain"`; the provider quick filter cannot distinguish a real vendor |

## Where this example is stronger than the siblings

Verified against the pinned versions (traceloop-sdk / instrumentation-langchain 0.62.1):

1. **Modern message content (AR-011/AR-012).** `span_utils.set_chat_request` / `set_chat_response` emit `gen_ai.input.messages` / `gen_ai.output.messages` unconditionally (gated only by content capture), so DT gets the current-spec message shape. crewai and litellm fall back to the deprecated `gen_ai.prompt.*` / `gen_ai.completion.*`.
2. **Native token attribute names (AR-006/AR-007).** `callback_handler` maps the fixture's `token_usage` onto `gen_ai.usage.input_tokens` / `output_tokens` directly — no `prompt_tokens`/`completion_tokens` fallback like the siblings.
3. **`gen_ai.conversation.id` (AR-041).** Set explicitly by `FixtureSpanProcessor` (stable UUIDv5 of the case name), so multi-turn cases group into a thread. crewai/litellm mark this as missing.
4. **`should_enrich_metrics=True` on the tenant path** plus delta temporality set from the SDK — the metric pipeline is configured, unlike crewai (which cannot set the flag at all).

## Notes

### Metrics without a collector (genuine uncertainty)
The LangChain instrumentor creates and records both GenAI client histograms — `gen_ai.client.operation.duration` (AR-025) and `gen_ai.client.token.usage` (AR-044) — on the MeterProvider that `Traceloop.init` configures. With `should_enrich_metrics=True`, `disable_batch=True`, delta temporality, and `api_endpoint` pointed at `…/api/v2/otlp`, the SDK is set up to ship metrics **directly to the tenant with no collector**. This *should* populate the latency/cost metric charts, but it is **not verified here**: (a) the example's e2e test uses `auditSpan`, which checks span attributes only — it never polls for the metrics; and (b) unlike the crewai/litellm collector path, nothing external re-aggregates or converts temporality, so correct histogram delivery depends entirely on Traceloop's direct OTLP metric exporter and DT accepting delta OTLP histograms. Treat the metric-backed charts as "configured but unconfirmed," not a clean pass.

### Provider identity is the framework, not a vendor
Because the model is a `FakeListChatModel`, `detect_vendor_from_class` returns the `"langchain"` default. The provider-identity gate (AR-001/AR-002) passes on attribute *presence*, but every span reports `gen_ai.provider.name = "langchain"`. There is no real inference vendor and no `gen_ai.system`. This is honest for a fixture replayer, but it means the "Provider" filter/dimension carries no real vendor signal.

### Custom grounding attributes are a dt-evals contract, not semconv
`gen_ai.context` and `gen_ai.reference` are **non-standard** attributes stamped by `FixtureSpanProcessor` for the grounding evaluators (faithfulness, hallucination, context-relevance, summarization-quality). They are not in the OTel GenAI semconv and not in any baseline profile. dt-evals must map `spanFields.context: gen_ai.context` to consume them. Also note the system prompt is emitted as `gen_ai.system_instructions` (plural, AR-043) while dt-evals' default expects the singular `gen_ai.system_instruction` — map it if a metric needs the system prompt.

### Synthetic model & usage
`gen_ai.request.model` (`gpt-4o-mini`) and `gen_ai.usage.*` are real attributes on real spans but not real inferences — a fixed model default and a deterministic char-count token estimate. They make the spans production-shaped for regression assertions; the evaluators themselves do not read them.

## What to fix / notes

1. **Metric delivery — now asserted by the suite.** The e2e test uses `auditSpanWithMetrics` and polls both `gen_ai.client.operation.duration` (AR-025) and `gen_ai.client.token.usage` (AR-044) for `service.name == "dt-evals-fixtures"`. This resolves the previous open question: a green run proves the metrics reach the tenant over direct OTLP with no collector; a red run means the direct-OTLP metric path does not deliver and the app would need a collector (or the assertion relaxed to `auditSpan`).
2. **Provider value.** If a realistic provider dimension matters for the fixtures, set `gen_ai.provider.name` (or `gen_ai.system`) explicitly in `FixtureSpanProcessor` to a chosen vendor (e.g. `openai`) instead of the `"langchain"` default. Otherwise document that the provider filter is intentionally the framework.
3. **`gen_ai.agent.name` / `llm.request.type` / `gen_ai.request.temperature` absent** — expected for a plain chat invoke; only worth adding if the fixtures are extended to exercise agent or parameterized-request views.

> Content capture is gated by `TRACELOOP_TRACE_CONTENT` (verified against instrumentation-langchain 0.62.1: `should_send_prompts()` reads only this var). The generic `OTEL_SEMCONV_STABILITY_OPT_IN` / `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` flags are **not** read on the LangChain path — `tracing.py` sets `TRACELOOP_TRACE_CONTENT=true` accordingly.
