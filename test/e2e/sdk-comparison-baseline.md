# SDK Comparison Baseline: How To Use

This file explains how AI agents and humans should use:
- `test/e2e/sdk-comparison-baseline.json`

Goal: make SDK/framework comparisons deterministic and consistent.

## What This Baseline Is

`sdk-comparison-baseline.json` (v1.2.0) is the single source of truth for pass/fail comparison rules against the current Dynatrace AI Observability app expectations.

It contains:
- Core pass/fail rules (`must_have_any`, `must_have_all`)
- Provider-specific checks (Azure, Bedrock, OpenAI, Google, NVIDIA, Kong)
- Normalization/equivalence rules (modern vs legacy fields)
- Attribute ownership and usage context
- Non-SDK enrichment fields that must not fail SDK checks
- Per-view dependency rules (`view_rules`) for modeling gates, narrowing filters, and fallbacks
- Silent failure modes: attributes whose absence causes empty charts rather than visible errors
- Per-profile dashboard mapping: which Dynatrace dashboard each profile targets
- Provider-native metric catalogs: Kong Gateway (KO-001..KO-004) and NVIDIA NIM (NV-001..NV-008)
- Dashboard gaps: attributes defined in the baseline but not yet visualised in any dashboard

## How AI Should Use It

1. Load `sdk-comparison-baseline.json` first. Check `changelog` to confirm you are on v1.2.0.
2. Build an emitted-attributes set for the SDK under test.
3. Apply contract rules in this order:
   - `profile_selection.profiles` — determine which profile applies and which dashboard it targets
   - `profile_selection.scenario_overrides` (higher precedence than profiles)
   - `must_have_any`
   - `must_have_all`
   - `required_resolution` (primary-with-fallback enforcement)
   - `view_rules` for any app view you want to validate specifically
   - provider-specific section for active provider profile only
   - optional/recommended checks as non-blocking unless policy says otherwise
4. Apply normalization rules before deciding failures:
   - any-of equivalents
   - legacy fallback equivalents
5. Ignore fields listed under `non_sdk_fields` for SDK pass/fail.
6. For `kong` and `nvidia` profiles: validate `provider_metrics` (KO-*/NV-*) separately from span-based `must_have_all` checks. The Kong dashboard is entirely metrics-driven; skip span checks that cannot be satisfied from metrics alone.
7. Output a final verdict with:
   - PASS/FAIL/PARTIAL
   - failing attributes only
   - provider profile used + dashboard targeted
   - silent failure warnings (see below)

## Profiles & Dashboard Mapping

Each profile maps to a specific dashboard in `genai-observability/documents/`. Use the profile that matches the provider under test.

| Profile | Dashboard | Description |
|---|---|---|
| `generic` | `abmodelversioning.dashboard.json` | Provider-agnostic; any OTel-compliant SDK. Covers all_genai_views, prompts, cost, latency, service_health. |
| `openai` | `openai.dashboard.json` | Extends generic + OpenAI prompt-caching attributes (AR-022, AR-023). |
| `azure` | `azureai.dashboard.json` | Extends generic + Azure content filter attributes (AR-015, AR-016). |
| `bedrock` | `bedrock.dashboard.json` | Extends generic + Bedrock guardrail, caching, and contextual grounding attributes. |
| `google` | `google.dashboard.json` | Extends generic; no additional provider-specific attributes required. |
| `nvidia` | `nvidia.dashboard.json` | Extends generic + NVIDIA NIM Prometheus metrics (NV-001..NV-008). |
| `kong` | `kong.dashboard.json` | Kong AI Gateway; primarily Kong Prometheus metrics (KO-001..KO-004) with minimal span checks. |

## Recommended AI Output Shape

Use this structure in reports:
- `profile`: `generic | azure | bedrock | openai | google | nvidia | kong`
- `dashboard_targeted`: dashboard filename from profile mapping above
- `result`: `PASS | FAIL | PARTIAL`
- `failed_required`: list
- `failed_provider_specific`: list
- `missing_recommended`: list
- `missing_optional`: list
- `silent_failures`: list — attributes absent that cause empty charts with no visible error
- `dashboard_coverage`: per-view table showing which dashboard tiles would be populated vs empty
- `notes`: list

## Silent Failure Modes

These attributes do **not** cause a FAIL verdict by themselves, but their absence degrades specific app features invisibly — dashboards show zero/empty with no error message. Flag them in `silent_failures` in the output report.

| Attribute | Rule ID | Feature degraded | Failure mode |
|---|---|---|---|
| `gen_ai.client.operation.duration` | AR-025 | All latency charts | Empty charts, no error shown |
| `gen_ai.client.token.usage` (metric) | AR-044 | All cost dashboard tiles | $0 shown silently; tile does not indicate missing metric |
| `gen_ai.token.type` (metric dimension) | AR-024 | Cost dashboard input/output lanes | Cost shown as undifferentiated total |
| `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens` (all four token fields missing) | AR-006/AR-007 | Cost dashboard | $0 cost shown silently |
| `gen_ai.evaluation.score.label` | AR-029 | Evaluation results tab | Verdict column blank |
| `gen_ai.agent.name` | AR-010 | Agent vs LLM distinction | All spans classified as LLM |
| `gen_ai.prompt_caching` / `gen_ai.cache.type` | AR-022/AR-023 | Cache hit rate chart | 0% shown silently |
| `gen_ai.conversation.id` | AR-041 | Conversation thread grouping | Prompts view shows no thread grouping |
| `span.status_code` | AR-047 | Service health tile | All requests appear successful; no error signal |

## Human-Readable Attribute Summary Table

This table is the human-readable view of the baseline contract and should be used for ticket discussions and review comments.

Model overview:
- `attributes`: field catalog (what a field is)
- `comparison_contract.required_resolution`: primary/fallback semantics
- `comparison_contract.view_rules`: where and how fields are actually used in the app

Profile precedence:
- If a scenario override exists in `profile_selection.scenario_overrides`, run/skip profiles from the override.
- Otherwise, evaluate by selected profile (`generic`, `azure`, `bedrock`, `openai`, `google`, `nvidia`, `kong`).

### Core & Service

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.provider.name` | AR-002 | required (primary) | base_ai_span_filter, provider_quick_filter, service_explorer_table, distributed_tracing_intent |
| `gen_ai.system` | AR-001 | required (deprecated fallback for `gen_ai.provider.name`) | base_ai_span_filter, provider_quick_filter, service_explorer_table, distributed_tracing_intent, onboarding_validation |
| `service.name` | AR-003 | required | service_quick_filter, service_explorer_table, onboarding_validation |
| `gen_ai.request.model` | AR-004 | required | prompts_table, distributed_tracing_intent, onboarding_validation |
| `gen_ai.response.model` | AR-005 | required | model_quick_filter, service_explorer_table, overview_charts, distributed_tracing_intent |
| `span.status_code` | AR-047 | recommended | service_health tile in all provider dashboards — values: `ok`, `error`, `unset`. Emitted automatically by OTel SDKs. |

> **Provider identity note:** `gen_ai.system` is deprecated in OTel semconv in favor of `gen_ai.provider.name`. The app's DQL uses `coalesce(gen_ai.system, gen_ai.provider.name)` checking the old field first only for backward compatibility with older SDKs. Prefer `gen_ai.provider.name` in all new instrumentation. The `must_have_any` gate passes if either is present.

### Tokens & Performance

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.usage.input_tokens` | AR-006 | required (primary) | prompts_table, service_explorer_table, overview_charts, cost_dashboard |
| `gen_ai.usage.output_tokens` | AR-007 | required (primary) | prompts_table, service_explorer_table, overview_charts, cost_dashboard |
| `gen_ai.usage.prompt_tokens` | AR-026 | optional (deprecated fallback for AR-006) | cost_dashboard |
| `gen_ai.usage.completion_tokens` | AR-027 | optional (deprecated fallback for AR-007) | cost_dashboard |
| `gen_ai.token.type` | AR-024 | recommended | cost_dashboard — splits cost lanes; values: `input`, `output`, `cache_read`, `cache_creation` |
| `gen_ai.client.operation.duration` | AR-025 | required | latency_charts — p99 and mean latency (OTel histogram metric) |
| `gen_ai.client.token.usage` | AR-044 | recommended | cost_dashboard — OTel counter metric; used as `timeseries sum(gen_ai.client.token.usage)` filtered by `gen_ai.token.type` dimension. Distinct from the span attributes AR-006/AR-007. Missing → all cost tiles show $0 silently. |

### Operations & Agents

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.operation.name` | AR-008 | recommended | operation_breakdown, trace_analysis |
| `gen_ai.agent.name` | AR-010 | recommended | agent_quick_filter, overview_charts |
| `llm.request.type` | AR-009 | optional | distributed_tracing_intent |

### Content

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.input.messages` | AR-011 | optional (primary) | prompts_table |
| `gen_ai.output.messages` | AR-012 | optional (primary) | prompts_table |
| `gen_ai.prompt.0.content` | AR-013 | optional (removed from semconv, legacy fallback for AR-011) | prompts_table, distributed_tracing_intent, onboarding_validation |
| `gen_ai.completion.0.content` | AR-014 | optional (removed from semconv, legacy fallback for AR-012) | prompts_table, distributed_tracing_intent |
| `gen_ai.system_instructions` | AR-043 | optional | prompts_table |
| `gen_ai.conversation.id` | AR-041 | optional | prompts_table — groups spans into conversation threads |
| `gen_ai.request.temperature` | AR-042 | optional | model_comparison_dashboard — display only |

### Guardrails (Azure)

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.prompt.prompt_filter_results` | AR-015 | provider-specific (azure) | guardrail_overview_cards |
| `gen_ai.completion.content_filter_results` | AR-016 | provider-specific (azure) | guardrail_overview_cards |

### Guardrails (Bedrock)

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.bedrock.guardrail.activation` | AR-017 | provider-specific (bedrock) | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.content` | AR-018 | provider-specific (bedrock) | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.sensitive_info` | AR-019 | provider-specific (bedrock) | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.topics` | AR-020 | provider-specific (bedrock) | guardrail_overview_cards — **⚠️ defined but not visualised in bedrock.dashboard.json** |
| `gen_ai.bedrock.guardrail.words` | AR-021 | provider-specific (bedrock) | guardrail_overview_cards — **⚠️ defined but not visualised in bedrock.dashboard.json** |
| `gen_ai.bedrock.guardrail.contextual` | AR-040 | provider-specific (bedrock) | guardrail_overview_cards — contextual grounding score |
| `gen_ai.guardrail.grounding_type` | AR-046 | provider-specific (bedrock) | guardrail_overview_cards — metric dimension on AR-040; values: `GROUNDING`, `RELEVANCE`. Splits grounding vs relevance tiles. |

### Caching (OpenAI / Bedrock)

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.prompt_caching` | AR-022 | provider-specific (openai, bedrock) | cached_vs_non_cached_chart — span attribute; values: `read` for cache hit |
| `gen_ai.cache.type` | AR-023 | provider-specific (openai, bedrock) | cached_vs_non_cached_chart — span attribute; values: `read`, `write` |
| `gen_ai.prompt.caching` | AR-045 | provider-specific (bedrock) | bedrock_cache_tiles — **metric** (distinct from AR-022); used as `timeseries sum(gen_ai.prompt.caching)` filtered by `gen_ai.cache.type` to compute cache-read/write token savings |

### Evaluation Results

Evaluation data arrives as **bizevents** (not spans). The gate is `event.type == 'gen_ai.evaluation.result'`.

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `event.type` | AR-049 | required (bigevent gate) | Filters bigevent streams; known values: `gen_ai.evaluation.result` (VR-017), `gen_ai.auditing` (VR-018) |
| `gen_ai.evaluation.result` | AR-036 | optional | evaluation_results — bizevent type gate value |
| `gen_ai.evaluation.name` | AR-028 | optional | evaluation_results — dedup key |
| `gen_ai.evaluation.score.label` | AR-029 | optional | evaluation_results — pass/fail verdict |
| `gen_ai.evaluation.score.value` | AR-030 | optional | evaluation_results — numeric score |
| `gen_ai.evaluation.method` | AR-031 | optional | evaluation_results (e.g. `llm_as_judge`) |
| `gen_ai.evaluation.scoring_format` | AR-032 | optional | evaluation_results (e.g. `binary`, `numeric`) |
| `gen_ai.evaluation.explanation` | AR-033 | optional | evaluation_results |
| `gen_ai.evaluation.input.question` | AR-034 | optional | evaluation_results |
| `gen_ai.evaluation.input.answer` | AR-035 | optional | evaluation_results |
| `gen_ai.evaluation.type` | AR-037 | optional | evaluation_results (`ready_made`, `custom`) |
| `gen_ai.evaluation.version` | AR-038 | optional | evaluation_results |
| `gen_ai.evaluation.spec_id` | AR-039 | optional | evaluation_results |

### Audit Trail

Audit trail data arrives as **bizevents** (not spans). The gate is `event.type == 'gen_ai.auditing'`.

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.model` | AR-048 | optional | audit_trail — bigevent field; groups audit events by model. Distinct from span attributes AR-004/AR-005. |

### Non-SDK Fields (ignore for pass/fail)

| Attribute | Rule ID | Source |
|---|---|---|
| `dt.smartscape.service` | NS-001 | dynatrace_enrichment |
| `dt.agent.module.type` | NS-002 | dynatrace_enrichment |

### Kong Gateway Metrics (KO-001..KO-004)

These are Prometheus metrics emitted by the Kong AI Gateway — not OTel span attributes. Validated separately from span-based checks. Only applicable when profile = `kong`.

| Metric | Rule ID | Type | Dimensions | Used By |
|---|---|---|---|---|
| `kong_ai_llm_requests_total` | KO-001 | counter | `ai_provider`, `ai_model` | kong_dashboard — request volume by provider/model |
| `kong_ai_llm_tokens_total` | KO-002 | counter | `ai_model`, `token_type` (`total_tokens`, `completion_tokens`, `prompt_tokens`) | kong_dashboard — token consumption; note `token_type` values differ from OTel `gen_ai.token.type` |
| `kong_ai_llm_provider_latency_ms` | KO-003 | histogram | — | kong_dashboard — LLM provider latency |
| `kong_kong_latency_ms` | KO-004 | histogram | `service`, `route` | kong_dashboard — gateway processing latency |

### NVIDIA NIM Metrics (NV-001..NV-008)

These are Prometheus metrics emitted by the NVIDIA NIM inference server — not OTel span attributes. Validated separately from span-based checks. Only applicable when profile = `nvidia`.

| Metric | Rule ID | Type | Dimensions | Used By |
|---|---|---|---|---|
| `e2e_request_latency_seconds` | NV-001 | histogram | `model_name` | nvidia_dashboard — end-to-end inference latency |
| `request_success_total` | NV-002 | counter | — | nvidia_dashboard — total successful requests |
| `request_prompt_tokens` | NV-003 | counter | — | nvidia_dashboard — input token volume |
| `request_generation_tokens` | NV-004 | counter | — | nvidia_dashboard — output token volume |
| `time_to_first_token_seconds` | NV-005 | histogram | — | nvidia_dashboard — streaming TTFT latency |
| `generation_tokens_total` | NV-006 | counter | `model_name` | nvidia_dashboard — generation throughput (rate: 1s) |
| `gpu_cache_usage_perc` | NV-007 | gauge | — | nvidia_dashboard — KV-cache utilisation % |
| `num_requests_running` | NV-008 | gauge | — | nvidia_dashboard — in-flight request concurrency |

Primary/fallback enforcement:
- Required checks must enforce primary fields first.
- Deprecated fields only satisfy checks when the mapped primary field is missing.
- Implement according to `comparison_contract.required_resolution` in `sdk-comparison-baseline.json`.

## Dashboard Gaps

Attributes defined in the baseline that are present in the SDK contract but **not yet visualised** in any dashboard tile. Report these separately from silent failures — they represent missing dashboard coverage, not missing SDK instrumentation.

| Attribute | Rule ID | Gap |
|---|---|---|
| `gen_ai.bedrock.guardrail.topics` | AR-020 | Defined for Bedrock profile; no tile in `bedrock.dashboard.json` queries this attribute |
| `gen_ai.bedrock.guardrail.words` | AR-021 | Defined for Bedrock profile; no tile in `bedrock.dashboard.json` queries this attribute |

## View Rule Examples

These rules model app behavior better than a flat required/optional list.

### `all_genai_views`
- Inclusion gate: `gen_ai.provider.name` OR `gen_ai.system` (deprecated fallback)
- Either satisfies the gate; `gen_ai.provider.name` is the preferred modern attribute.
- Meaning: span must first qualify as a GenAI span at all.

### `service_health`
- Depends on: `all_genai_views`
- Uses `span.status_code` to split requests into Successful / Failed
- Expression: `if(span.status_code == "error", "Failed", else: "Successful")`
- Missing `span.status_code` → all requests appear successful; no error signal in health tile

### `prompts_view`
- Depends on: `all_genai_views`
- Narrowing filter: `llm.request.type` is null OR in (`chat`, `completion`)
- Prompt resolution: prefer `gen_ai.input.messages`, fallback to deprecated `gen_ai.prompt.0.content`
- Completion resolution: prefer `gen_ai.output.messages`, fallback to deprecated `gen_ai.completion.0.content`

### `overview_prompts_count`
- Depends on: `all_genai_views`
- Same `llm.request.type` narrowing as prompts view

### `distributed_tracing_intent`
- Depends on: `all_genai_views`
- `llm.request.type` is display metadata only, not a hard inclusion gate

### `cost_dashboard`
- Depends on: `all_genai_views`
- Requires `gen_ai.client.token.usage` metric (AR-044) — different from span attributes AR-006/AR-007
- `gen_ai.token.type` (AR-024) as metric dimension splits cost into input vs output lanes — missing causes silent undifferentiated total
- Missing all token fields → $0 shown with no error
- Span-based token attributes (AR-006/AR-007) feed the prompts table but **not** the cost metric tiles

### `latency_charts`
- Depends on: `all_genai_views`
- Requires `gen_ai.client.operation.duration` (AR-025) OTel metric for p99/mean latency
- Missing → all latency charts empty with no error surfaced
- Alternative: span `duration` is used in the per-provider health tiles but is not the same as the latency chart metric

### `guardrail_overview_cards`
- Depends on: `all_genai_views`
- Azure and Bedrock attributes are provider-specific rules, not global requirements
- Bedrock includes the contextual grounding score (`gen_ai.bedrock.guardrail.contextual`, AR-040)
- `gen_ai.guardrail.grounding_type` (AR-046) is the metric dimension that separates grounding from relevance score tiles
- AR-020 and AR-021 are expected from the Bedrock SDK but not yet visualised in any dashboard tile

### `cached_vs_non_cached_chart`
- Depends on: `all_genai_views`
- OpenAI caching attributes are provider-specific rules, not global requirements
- `gen_ai.prompt_caching` (AR-022) is the span attribute; `gen_ai.prompt.caching` (AR-045) is the Bedrock metric

### `evaluation_results`
- Depends on: `all_genai_views`
- Data source: bizevents only, gated on `event.type == 'gen_ai.evaluation.result'` (AR-049)
- Dedup key: `['span_id', 'gen_ai.evaluation.name']`
- Verdict expression: `if(countIf(gen_ai.evaluation.score.label != "pass") > 0, "fail", else: "pass")`

### `audit_trail`
- Data source: bizevents only, gated on `event.type == 'gen_ai.auditing'` (AR-049)
- Independent of the span pipeline; requires separate bigevent emission
- `gen_ai.model` (AR-048) is the grouping key for audit events

### `bedrock_cache_tiles`
- Depends on: `all_genai_views`
- Uses `gen_ai.prompt.caching` metric (AR-045) — a Prometheus-style counter, not the span attribute AR-022
- Filtered by `gen_ai.cache.type` dimension (`read` / `write`) to compute cache savings cost

## Minimal Decision Examples

### Generic profile (→ abmodelversioning.dashboard.json)
- PASS if:
  - `gen_ai.provider.name` is present (or deprecated fallback `gen_ai.system` if primary is missing), AND
  - all `must_have_all` fields are present (or their declared equivalents from `equivalents_any_of`).
- Ignore Azure/Bedrock/OpenAI provider-specific lists.
- Flag missing recommended fields (`gen_ai.client.operation.duration`, `gen_ai.client.token.usage`, `gen_ai.token.type`, `gen_ai.agent.name`) as `silent_failures` or `missing_recommended`.
- Dashboard coverage: service_health tile works only if `span.status_code` is present.

### Scenario override (higher precedence)
- If `profile_selection.scenario_overrides` exists for the scenario, use that run/skip profile set.
- Example: `openinference-basic` must not run Bedrock or Azure checks.

### Azure profile (→ azureai.dashboard.json)
- Must pass generic profile first.
- Then also require Azure provider-specific attributes (AR-015, AR-016).

### Bedrock profile (→ bedrock.dashboard.json)
- Must pass generic profile first.
- Then also require Bedrock provider-specific attributes (AR-017, AR-018, AR-019 required; AR-020, AR-021, AR-040, AR-045, AR-046 optional).
- Note: AR-020 and AR-021 are in the baseline but not visualised in any dashboard tile — presence is expected from the SDK but their absence does not degrade any dashboard.

### OpenAI profile (→ openai.dashboard.json)
- Must pass generic profile first.
- Then also require OpenAI provider-specific attributes (AR-022, AR-023).

### Google profile (→ google.dashboard.json)
- Must pass generic profile first.
- No additional provider-specific attributes required.

### NVIDIA profile (→ nvidia.dashboard.json)
- Must pass generic profile first (span-based checks for spans emitted via OpenAI-compatible NIM endpoint).
- Also validate NVIDIA NIM Prometheus metrics (NV-001..NV-008) — check that the NIM server is configured to export these metrics to DT.

### Kong profile (→ kong.dashboard.json)
- The Kong dashboard is primarily metrics-driven; span-based `must_have_all` checks apply only to the service-health tile.
- Validate Kong Prometheus metrics (KO-001..KO-004) as the primary check.
- `gen_ai.provider.name` / `gen_ai.system` must still be present on any spans that flow through Kong for the service-health tile to work.

## Important Guardrails

- Do not infer new rules outside this file during automated comparison.
- If runtime evidence conflicts with baseline, report as "baseline drift" instead of silently changing verdict logic.
- Update the baseline file first, then re-run comparisons.
- Always check `changelog` in `sdk-comparison-baseline.json` to confirm you are reading the current version before running a comparison.
- For AR-020 and AR-021: their absence from a Bedrock SDK does NOT degrade any current dashboard. Report them as `dashboard_gaps` (SDK should emit them; dashboard does not yet visualise them) rather than `silent_failures`.
- `gen_ai.client.token.usage` (AR-044) is a metric, not a span attribute. Its presence cannot be inferred from span traces alone — it requires a metrics pipeline (e.g. `should_enrich_metrics=True` in Traceloop, or a custom `MeterProvider`).
