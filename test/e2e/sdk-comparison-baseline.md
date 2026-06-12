# SDK Comparison Baseline: How To Use

This file explains how AI agents and humans should use:
- `test/e2e/sdk-comparison-baseline.json`

Goal: make SDK/framework comparisons deterministic and consistent.

## What This Baseline Is

`sdk-comparison-baseline.json` is the single source of truth for pass/fail comparison rules against the current Dynatrace AI Observability app expectations.

It contains:
- Core pass/fail rules (`must_have_any`, `must_have_all`)
- Provider-specific checks (Azure, Bedrock, OpenAI)
- Normalization/equivalence rules (modern vs legacy fields)
- Attribute ownership and usage context
- Non-SDK enrichment fields that must not fail SDK checks

## How AI Should Use It

1. Load `sdk-comparison-baseline.json` first.
2. Build an emitted-attributes set for the SDK under test.
3. Apply contract rules in this order:
   - `profile_selection` (scenario overrides first)
   - `must_have_any`
   - `must_have_all`
   - `required_resolution` (primary-with-fallback enforcement)
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

## Recommended AI Output Shape

Use this structure in reports:
- `profile`: `generic | azure | bedrock | openai`
- `result`: `PASS | FAIL | PARTIAL`
- `failed_required`: list
- `failed_provider_specific`: list
- `missing_optional`: list
- `notes`: list

## Human-Readable Attribute Summary Table

This table is the human-readable view of the baseline contract and should be used for ticket discussions and review comments.

Profile precedence:
- If a scenario override exists in `profile_selection.scenario_overrides`, run/skip profiles from the override.
- Otherwise, evaluate by selected profile (`generic`, `azure`, `bedrock`, `openai`).

| Attribute | Required Level | Used By Visuals |
|---|---|---|
| `gen_ai.provider.name` | required (primary) | base_ai_span_filter, provider_quick_filter, service_explorer_table, distributed_tracing_intent |
| `gen_ai.system` | deprecated fallback for `gen_ai.provider.name` | base_ai_span_filter, provider_quick_filter, service_explorer_table, distributed_tracing_intent, onboarding_validation |
| `service.name` | required | service_quick_filter, service_explorer_table, onboarding_validation |
| `gen_ai.request.model` | required | prompts_table, distributed_tracing_intent, onboarding_validation |
| `gen_ai.response.model` | required | model_quick_filter, service_explorer_table, overview_charts, distributed_tracing_intent |
| `gen_ai.usage.input_tokens` | required (primary) | prompts_table, service_explorer_table, overview_charts, distributed_tracing_intent |
| `gen_ai.usage.prompt_tokens` | deprecated fallback for `gen_ai.usage.input_tokens` | service_explorer_table, overview_charts |
| `gen_ai.usage.output_tokens` | required (primary) | prompts_table, service_explorer_table, overview_charts |
| `gen_ai.usage.completion_tokens` | deprecated fallback for `gen_ai.usage.output_tokens` | service_explorer_table |
| `gen_ai.operation.name` | recommended | operation_breakdown, trace_analysis |
| `gen_ai.agent.name` | recommended | agent_quick_filter, overview_charts |
| `llm.request.type` | optional | distributed_tracing_intent |
| `gen_ai.input.messages` | optional (primary content field) | prompts_table |
| `gen_ai.prompt.0.content` | deprecated fallback for `gen_ai.input.messages` | prompts_table, distributed_tracing_intent, onboarding_validation |
| `gen_ai.output.messages` | optional (primary content field) | prompts_table |
| `gen_ai.completion.0.content` | deprecated fallback for `gen_ai.output.messages` | prompts_table, distributed_tracing_intent |
| `gen_ai.prompt.prompt_filter_results` | provider-specific | guardrail_overview_cards |
| `gen_ai.completion.content_filter_results` | provider-specific | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.activation` | provider-specific | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.content` | provider-specific | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.sensitive_info` | provider-specific | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.topics` | provider-specific | guardrail_overview_cards |
| `gen_ai.bedrock.guardrail.words` | provider-specific | guardrail_overview_cards |
| `gen_ai.prompt_caching` | provider-specific | cached_vs_non_cached_chart |
| `gen_ai.cache.type` | provider-specific | cached_vs_non_cached_chart |
| `dt.smartscape.service` | non-sdk enrichment | service_quick_filter, service_explorer_table |
| `dt.agent.module.type` | non-sdk enrichment | service_explorer_table |

Primary/fallback enforcement:
- Required checks must enforce primary fields first.
- Deprecated fields only satisfy checks when the mapped primary field is missing.
- Implement according to `comparison_contract.required_resolution` in `sdk-comparison-baseline.json`.

## Minimal Decision Examples

### Generic profile
- PASS if:
   - primary provider field `gen_ai.provider.name` is present (or deprecated fallback `gen_ai.system` if primary is missing), AND
  - all `must_have_all` fields are present.
- Ignore Azure/Bedrock/OpenAI provider-specific lists.

### Scenario override (higher precedence)
- If `profile_selection.scenario_overrides` exists for the scenario, use that run/skip profile set.
- Example: `openinference-basic` must not run Bedrock or Azure checks.

### Azure profile
- Must pass generic profile first.
- Then also require Azure provider-specific attributes.

### Bedrock profile
- Must pass generic profile first.
- Then also require Bedrock provider-specific attributes.

### OpenAI profile
- Must pass generic profile first.
- Then also require OpenAI provider-specific attributes.

## Important Guardrails

- Do not infer new rules outside this file during automated comparison.
- If runtime evidence conflicts with baseline, report as "baseline drift" instead of silently changing verdict logic.
- Update the baseline file first, then re-run comparisons.
