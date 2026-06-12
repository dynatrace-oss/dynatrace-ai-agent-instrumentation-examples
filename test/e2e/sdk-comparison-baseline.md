# SDK Comparison Baseline: How To Use

This file explains how AI agents and humans should use:
- `test/e2e/sdk-comparison-baseline.json`

Goal: make SDK/framework comparisons deterministic and consistent.

## What This Baseline Is

`sdk-comparison-baseline.json` (v1.1.1) is the single source of truth for pass/fail comparison rules against the current Dynatrace AI Observability app expectations.

It contains:
- Core pass/fail rules (`must_have_any`, `must_have_all`)
- Provider-specific checks (Azure, Bedrock, OpenAI)
- Normalization/equivalence rules (modern vs legacy fields)
- Attribute ownership and usage context
- Non-SDK enrichment fields that must not fail SDK checks
- Per-view dependency rules (`view_rules`) for modeling gates, narrowing filters, and fallbacks
- Silent failure modes: attributes whose absence causes empty charts rather than visible errors

## How AI Should Use It

1. Load `sdk-comparison-baseline.json` first.
2. Build an emitted-attributes set for the SDK under test.
3. Apply contract rules in this order:
   - `profile_selection` (scenario overrides first)
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
6. Output a final verdict with:
   - PASS/FAIL/PARTIAL
   - failing attributes only
   - provider profile used
   - silent failure warnings (see below)

## Recommended AI Output Shape

Use this structure in reports:
- `profile`: `generic | azure | bedrock | openai`
- `result`: `PASS | FAIL | PARTIAL`
- `failed_required`: list
- `failed_provider_specific`: list
- `missing_recommended`: list
- `missing_optional`: list
- `silent_failures`: list — attributes absent that cause empty charts with no visible error
- `notes`: list

## Silent Failure Modes

These attributes do **not** cause a FAIL verdict by themselves, but their absence degrades specific app features invisibly — dashboards show zero/empty with no error message. Flag them in `silent_failures` in the output report.

| Attribute | Feature degraded | Failure mode |
|---|---|---|
| `gen_ai.client.operation.duration` | All latency charts | Empty charts, no error shown |
| `gen_ai.token.type` | Cost dashboard input/output lanes | Cost shown as undifferentiated total |
| `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens` (all four token fields missing) | Cost dashboard | $0 cost shown silently |
| `gen_ai.evaluation.score.label` | Evaluation results tab | Verdict column blank |
| `gen_ai.agent.name` | Agent vs LLM distinction | All spans classified as LLM |
| `gen_ai.prompt_caching` / `gen_ai.cache.type` | Cache hit rate chart | 0% shown silently |

## Human-Readable Attribute Summary Table

This table is the human-readable view of the baseline contract and should be used for ticket discussions and review comments.

Model overview:
- `attributes`: field catalog (what a field is)
- `comparison_contract.required_resolution`: primary/fallback semantics
- `comparison_contract.view_rules`: where and how fields are actually used in the app

Profile precedence:
- If a scenario override exists in `profile_selection.scenario_overrides`, run/skip profiles from the override.
- Otherwise, evaluate by selected profile (`generic`, `azure`, `bedrock`, `openai`).

### Core & Service

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.provider.name` | AR-002 | required (primary) | base_ai_span_filter, provider_quick_filter, service_explorer_table, distributed_tracing_intent |
| `gen_ai.system` | AR-001 | required (deprecated fallback for `gen_ai.provider.name`) | base_ai_span_filter, provider_quick_filter, service_explorer_table, distributed_tracing_intent, onboarding_validation |
| `service.name` | AR-003 | required | service_quick_filter, service_explorer_table, onboarding_validation |
| `gen_ai.request.model` | AR-004 | required | prompts_table, distributed_tracing_intent, onboarding_validation |
| `gen_ai.response.model` | AR-005 | required | model_quick_filter, service_explorer_table, overview_charts, distributed_tracing_intent |

> **Provider identity note:** `gen_ai.system` is deprecated in OTel semconv in favor of `gen_ai.provider.name`. The app's DQL uses `coalesce(gen_ai.system, gen_ai.provider.name)` checking the old field first only for backward compatibility with older SDKs. Prefer `gen_ai.provider.name` in all new instrumentation. The `must_have_any` gate passes if either is present.

### Tokens & Performance

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.usage.input_tokens` | AR-006 | required (primary) | prompts_table, service_explorer_table, overview_charts, cost_dashboard |
| `gen_ai.usage.output_tokens` | AR-007 | required (primary) | prompts_table, service_explorer_table, overview_charts, cost_dashboard |
| `gen_ai.usage.prompt_tokens` | AR-026 | optional (deprecated fallback for AR-006) | cost_dashboard |
| `gen_ai.usage.completion_tokens` | AR-027 | optional (deprecated fallback for AR-007) | cost_dashboard |
| `gen_ai.token.type` | AR-024 | recommended | cost_dashboard — splits cost lanes; values: `input`, `output`, `cache_read`, `cache_creation` |
| `gen_ai.client.operation.duration` | AR-025 | required | latency_charts — p99 and mean latency |

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
| `gen_ai.bedrock.guardrail.topics` | AR-020 | provider-specific (bedrock) | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.words` | AR-021 | provider-specific (bedrock) | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.contextual` | AR-040 | provider-specific (bedrock) | guardrail_overview_cards — contextual grounding score |

### Caching (OpenAI)

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.prompt_caching` | AR-022 | provider-specific (openai) | cached_vs_non_cached_chart |
| `gen_ai.cache.type` | AR-023 | provider-specific (openai) | cached_vs_non_cached_chart |

### Evaluation Results

Evaluation data arrives as **bizevents** (not spans). The gate is `event.type == 'gen_ai.evaluation.result'`.

| Attribute | Rule ID | Required Level | Used By Visuals |
|---|---|---|---|
| `gen_ai.evaluation.result` | AR-036 | optional | evaluation_results — bizevent type gate |
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

### Non-SDK Fields (ignore for pass/fail)

| Attribute | Rule ID | Source |
|---|---|---|
| `dt.smartscape.service` | NS-001 | dynatrace_enrichment |
| `dt.agent.module.type` | NS-002 | dynatrace_enrichment |

Primary/fallback enforcement:
- Required checks must enforce primary fields first.
- Deprecated fields only satisfy checks when the mapped primary field is missing.
- Implement according to `comparison_contract.required_resolution` in `sdk-comparison-baseline.json`.

## View Rule Examples

These rules model app behavior better than a flat required/optional list.

### `all_genai_views`
- Inclusion gate: `gen_ai.provider.name` OR `gen_ai.system` (deprecated fallback)
- Either satisfies the gate; `gen_ai.provider.name` is the preferred modern attribute.
- Meaning: span must first qualify as a GenAI span at all.

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
- Requires at least one token count field (input + output, or legacy equivalents)
- `gen_ai.token.type` splits cost into input vs output lanes — missing causes silent undifferentiated total
- Missing all token fields → $0 shown with no error

### `latency_charts`
- Depends on: `all_genai_views`
- Requires `gen_ai.client.operation.duration` for p99 / mean latency
- Missing → all latency charts empty with no error surfaced

### `guardrail_overview_cards`
- Depends on: `all_genai_views`
- Azure and Bedrock attributes are provider-specific rules, not global requirements
- Bedrock includes the contextual grounding score (`gen_ai.bedrock.guardrail.contextual`) in addition to the five counter fields

### `cached_vs_non_cached_chart`
- Depends on: `all_genai_views`
- OpenAI caching attributes are provider-specific rules, not global requirements

### `evaluation_results`
- Depends on: `all_genai_views`
- Data source: bizevents only, gated on `event.type == 'gen_ai.evaluation.result'`
- Dedup key: `['span_id', 'gen_ai.evaluation.name']`
- Verdict expression: `if(countIf(gen_ai.evaluation.score.label != "pass") > 0, "fail", else: "pass")`

## Minimal Decision Examples

### Generic profile
- PASS if:
  - `gen_ai.provider.name` is present (or deprecated fallback `gen_ai.system` if primary is missing), AND
  - all `must_have_all` fields are present (or their declared equivalents from `equivalents_any_of`).
- Ignore Azure/Bedrock/OpenAI provider-specific lists.
- Flag missing recommended fields (`gen_ai.client.operation.duration`, `gen_ai.token.type`, `gen_ai.agent.name`) as `silent_failures` or `missing_recommended`.

### Scenario override (higher precedence)
- If `profile_selection.scenario_overrides` exists for the scenario, use that run/skip profile set.
- Example: `openinference-basic` must not run Bedrock or Azure checks.

### Azure profile
- Must pass generic profile first.
- Then also require Azure provider-specific attributes.

### Bedrock profile
- Must pass generic profile first.
- Then also require Bedrock provider-specific attributes (including `gen_ai.bedrock.guardrail.contextual`).

### OpenAI profile
- Must pass generic profile first.
- Then also require OpenAI provider-specific attributes.

## Important Guardrails

- Do not infer new rules outside this file during automated comparison.
- If runtime evidence conflicts with baseline, report as "baseline drift" instead of silently changing verdict logic.
- Update the baseline file first, then re-run comparisons.
- Always check `changelog` in `sdk-comparison-baseline.json` to confirm you are reading the current version before running a comparison.
