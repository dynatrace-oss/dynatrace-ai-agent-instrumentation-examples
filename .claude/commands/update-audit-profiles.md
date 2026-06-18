# update-audit-profiles

Update the Go profile definitions in `test/e2e/audit_test.go` to match the current `test/e2e/sdk-comparison-baseline.json`.

## When to run

Run whenever `sdk-comparison-baseline.json` has changed (new AR-IDs added, attributes moved between required/optional, new profiles added, equivalents/fallbacks updated).

## Mapping: baseline JSON → Go code

### Files involved

| File | Role |
|------|------|
| `test/e2e/sdk-comparison-baseline.json` | Source of truth |
| `test/e2e/audit_test.go` | Profile definitions to update |

### Key baseline sections

| Baseline path | Used for |
|---------------|----------|
| `comparison_contract.profile_selection.profiles` | Profile names, which AR-IDs are required vs optional, which profiles extend generic |
| `comparison_contract.normalization.equivalents_any_of` | `AnyOf` lists on `AttributeCheck` (primary + canonical fallbacks) |
| `comparison_contract.normalization.legacy_fallbacks` | Additional `AnyOf` entries (legacy attribute names accepted as fallback) |
| `attributes[]` | Resolve AR-ID → attribute `name` |

### Step-by-step

1. **Read the baseline.** Parse `comparison_contract.profile_selection.profiles` to get the current required/optional AR-ID lists per profile.

2. **Resolve AR-IDs to attribute names.** For each AR-ID in a profile's lists, find the matching entry in `attributes[]` by `rule_id` and take its `name` field.

3. **Build `AnyOf` lists.** For each `AttributeCheck`:
   - Check `normalization.equivalents_any_of`: if the attribute's name appears in any group there, set `AnyOf` to that entire group (primary attribute first).
   - Check `normalization.legacy_fallbacks`: if the attribute's name is a key there, append the fallback names after the primary in `AnyOf`.
   - If neither applies, leave `AnyOf` empty (only `Name` is checked).

4. **Update `genericRequired` and `genericOptional`** to match the `generic` profile's `required_attributes` and `optional_attributes` lists exactly.

5. **Update provider profile extensions** (e.g. `BedrockProfile` in the `init()` func):
   - `additional_required_attributes` → appended to `genericRequired`
   - `additional_optional_attributes` → appended to `genericOptional`
   - Each profile that `extends: generic` follows this pattern.

6. **Add new profiles** if new profile names appear in the baseline that have no corresponding Go var. Use the `init()` pattern already used by `BedrockProfile`.

7. **Remove or rename profiles** if a profile was removed or renamed in the baseline.

## Existing Go structure (reference)

```
var genericRequired = []AttributeCheck{ ... }   // generic profile required
var genericOptional  = []AttributeCheck{ ... }   // generic profile optional
var GenericProfile   = Profile{...}              // assembled from above

var BedrockProfile Profile                       // declared at package level
func init() {                                    // built in init to avoid slice aliasing
    BedrockProfile = Profile{
        Name: "bedrock",
        Required: append(append([]AttributeCheck{}, genericRequired...),
            // additional_required_attributes for bedrock
        ),
        Optional: append(append([]AttributeCheck{}, genericOptional...),
            // additional_optional_attributes for bedrock
        ),
    }
}
```

Use the same `init()` pattern for any new provider profile. Do not mutate `genericRequired`/`genericOptional` in place — always copy with `append([]AttributeCheck{}, genericRequired...)`.

## What NOT to change

- `evaluateCheck`, `buildReport`, `writeReport`, `buildMarkdown`, `auditSpan`, `fetchTraceSpans`, `mergeSpans` — report engine, unrelated to profile definitions.
- The `RuleID` string format — use the exact string from the baseline `rule_id` field (e.g. `"AR-006"`). For the provider-identity pair AR-001/AR-002, keep the combined `"AR-001/AR-002"` rule ID as used in the existing code.
- Do not add or remove Go profiles that are not backed by a profile entry in the baseline.

## Verification

After updating:

```bash
cd test/e2e && go build ./...
```

Must compile clean. No test run required to verify profile structure.
