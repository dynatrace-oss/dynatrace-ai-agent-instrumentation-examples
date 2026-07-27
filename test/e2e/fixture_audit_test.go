package e2e

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"
)

// AttributeCheck defines one attribute to verify against a span.
// AnyOf lists the primary attribute plus accepted fallbacks in priority order.
// If AnyOf is empty only Name is checked.
type AttributeCheck struct {
	Name   string
	RuleID string
	AnyOf  []string
}

// AttributeResult is the outcome of one AttributeCheck.
type AttributeResult struct {
	RuleID       string `json:"rule_id"`
	Attribute    string `json:"attribute"`
	Status       string `json:"status"` // required: "pass"|"pass_via_fallback"|"fail"; optional: "present"|"present_via_fallback"|"absent"
	FallbackUsed string `json:"fallback_used,omitempty"`
}

// SpanReport holds the full audit result for one SDK/instrumentation run.
type SpanReport struct {
	SDK             string            `json:"sdk"`
	Instrumentation string            `json:"instrumentation"`
	Profile         string            `json:"profile"`
	Verdict         string            `json:"verdict"` // "FULL"|"PASS"|"FAIL"
	Note            string            `json:"note,omitempty"`
	Required        []AttributeResult `json:"required"`
	Optional        []AttributeResult `json:"optional"`
	GeneratedAt     string            `json:"generated_at"`
}

// Profile pairs required and optional checks for a baseline profile.
type Profile struct {
	Name     string
	Required []AttributeCheck
	Optional []AttributeCheck
}

// ---------------------------------------------------------------------------
// Baseline profile definitions — mirror sdk-comparison-baseline.json v1.2.1
// ---------------------------------------------------------------------------

var genericRequired = []AttributeCheck{
	{Name: "gen_ai.provider.name", RuleID: "AR-001/AR-002",
		AnyOf: []string{"gen_ai.provider.name", "gen_ai.system"}},
	{Name: "service.name", RuleID: "AR-003"},
	{Name: "gen_ai.request.model", RuleID: "AR-004"},
	{Name: "gen_ai.response.model", RuleID: "AR-005"},
	{Name: "gen_ai.usage.input_tokens", RuleID: "AR-006",
		AnyOf: []string{"gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens"}},
	{Name: "gen_ai.usage.output_tokens", RuleID: "AR-007",
		AnyOf: []string{"gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens"}},
}

var genericOptional = []AttributeCheck{
	{Name: "gen_ai.operation.name", RuleID: "AR-008"},
	{Name: "llm.request.type", RuleID: "AR-009"},
	{Name: "gen_ai.agent.name", RuleID: "AR-010"},
	{Name: "gen_ai.input.messages", RuleID: "AR-011",
		AnyOf: []string{"gen_ai.input.messages", "gen_ai.prompt.0.content"}},
	{Name: "gen_ai.output.messages", RuleID: "AR-012",
		AnyOf: []string{"gen_ai.output.messages", "gen_ai.completion.0.content"}},
	{Name: "gen_ai.token.type", RuleID: "AR-024"},
	{Name: "gen_ai.conversation.id", RuleID: "AR-041"},
	{Name: "gen_ai.request.temperature", RuleID: "AR-042"},
	{Name: "gen_ai.system_instructions", RuleID: "AR-043"},
	{Name: "gen_ai.client.token.usage", RuleID: "AR-044"},
	{Name: "span.status_code", RuleID: "AR-047"},
}

// GenericProfile covers all provider-agnostic dashboard views.
var GenericProfile = Profile{
	Name:     "generic",
	Required: genericRequired,
	Optional: genericOptional,
}

// BedrockProfile extends generic with AWS Bedrock guardrail attributes.
var BedrockProfile Profile

func init() {
	BedrockProfile = Profile{
		Name: "bedrock",
		Required: append(append([]AttributeCheck{}, genericRequired...),
			AttributeCheck{Name: "gen_ai.bedrock.guardrail.activation", RuleID: "AR-017"},
			AttributeCheck{Name: "gen_ai.bedrock.guardrail.content", RuleID: "AR-018"},
			AttributeCheck{Name: "gen_ai.bedrock.guardrail.sensitive_info", RuleID: "AR-019"},
		),
		Optional: append(append([]AttributeCheck{}, genericOptional...),
			AttributeCheck{Name: "gen_ai.bedrock.guardrail.topics", RuleID: "AR-020"},
			AttributeCheck{Name: "gen_ai.bedrock.guardrail.words", RuleID: "AR-021"},
			AttributeCheck{Name: "gen_ai.bedrock.guardrail.contextual", RuleID: "AR-040"},
			AttributeCheck{Name: "gen_ai.prompt.caching", RuleID: "AR-045"},
			AttributeCheck{Name: "gen_ai.guardrail.grounding_type", RuleID: "AR-046"},
		),
	}
}

// OpenAIProfile extends generic with OpenAI prompt-caching attributes.
var OpenAIProfile Profile

func init() {
	OpenAIProfile = Profile{
		Name:     "openai",
		Required: append([]AttributeCheck{}, genericRequired...),
		Optional: append(append([]AttributeCheck{}, genericOptional...),
			AttributeCheck{Name: "gen_ai.prompt_caching", RuleID: "AR-022"},
			AttributeCheck{Name: "gen_ai.cache.type", RuleID: "AR-023"},
		),
	}
}

// AzureProfile extends generic with Azure content filter attributes.
var AzureProfile Profile

func init() {
	AzureProfile = Profile{
		Name: "azure",
		Required: append(append([]AttributeCheck{}, genericRequired...),
			AttributeCheck{Name: "gen_ai.prompt.prompt_filter_results", RuleID: "AR-015"},
			AttributeCheck{Name: "gen_ai.completion.content_filter_results", RuleID: "AR-016"},
		),
		Optional: append([]AttributeCheck{}, genericOptional...),
	}
}

// ---------------------------------------------------------------------------
// Core functions
// ---------------------------------------------------------------------------

// evaluateCheck checks one attribute against a span record.
// required controls whether the absent status is "fail" or "absent".
func evaluateCheck(span map[string]interface{}, c AttributeCheck, required bool) AttributeResult {
	res := AttributeResult{RuleID: c.RuleID, Attribute: c.Name}

	candidates := c.AnyOf
	if len(candidates) == 0 {
		candidates = []string{c.Name}
	}

	for i, attr := range candidates {
		v, ok := span[attr]
		if !ok || v == nil || fmt.Sprint(v) == "" {
			continue
		}
		if i == 0 {
			if required {
				res.Status = "pass"
			} else {
				res.Status = "present"
			}
		} else {
			res.FallbackUsed = attr
			if required {
				res.Status = "pass_via_fallback"
			} else {
				res.Status = "present_via_fallback"
			}
		}
		return res
	}

	if required {
		res.Status = "fail"
	} else {
		res.Status = "absent"
	}
	return res
}

// buildReport evaluates all required and optional checks for a profile against
// a single span record. Results are sorted by RuleID for determinism.
func buildReport(sdk, instrumentation string, p Profile, span map[string]interface{}) SpanReport {
	required := make([]AttributeResult, len(p.Required))
	for i, c := range p.Required {
		required[i] = evaluateCheck(span, c, true)
	}
	sort.Slice(required, func(i, j int) bool { return required[i].RuleID < required[j].RuleID })

	optional := make([]AttributeResult, len(p.Optional))
	for i, c := range p.Optional {
		optional[i] = evaluateCheck(span, c, false)
	}
	sort.Slice(optional, func(i, j int) bool { return optional[i].RuleID < optional[j].RuleID })

	verdict := "PASS"
	for _, r := range required {
		if r.Status == "fail" {
			verdict = "FAIL"
			break
		}
	}
	if verdict == "PASS" {
		allOptPresent := true
		for _, r := range optional {
			if r.Status == "absent" {
				allOptPresent = false
				break
			}
		}
		if allOptPresent {
			verdict = "FULL"
		}
	}

	return SpanReport{
		SDK:             sdk,
		Instrumentation: instrumentation,
		Profile:         p.Name,
		Verdict:         verdict,
		Required:        required,
		Optional:        optional,
		GeneratedAt:     time.Now().UTC().Format(time.RFC3339),
	}
}

// writeReport writes both a JSON and a markdown report to test/e2e/reports/.
func writeReport(t *testing.T, r SpanReport) {
	t.Helper()
	dir := filepath.Join(repoRoot(), "test", "e2e", "reports")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Logf("warning: create reports dir: %v", err)
		return
	}
	base := filepath.Join(dir, r.SDK+"-"+r.Instrumentation)

	jsonData, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		t.Logf("warning: marshal report: %v", err)
		return
	}
	if err := os.WriteFile(base+".json", jsonData, 0o644); err != nil {
		t.Logf("warning: write report json: %v", err)
	}
	if err := os.WriteFile(base+".md", []byte(buildMarkdown(r)), 0o644); err != nil {
		t.Logf("warning: write report md: %v", err)
	}
}

func buildMarkdown(r SpanReport) string {
	verdictIcons := map[string]string{"FULL": "🌟", "PASS": "✅", "FAIL": "❌"}
	icon := verdictIcons[r.Verdict]

	var sb strings.Builder
	fmt.Fprintf(&sb, "# %s / %s — Span Audit Report\n\n", r.SDK, r.Instrumentation)
	fmt.Fprintf(&sb, "**Profile:** %s | **Verdict:** %s %s | **Generated:** %s\n\n",
		r.Profile, icon, r.Verdict, r.GeneratedAt)
	if r.Note != "" {
		fmt.Fprintf(&sb, "> **Note:** %s\n\n", r.Note)
	}

	sb.WriteString("## Required Attributes\n\n")
	sb.WriteString("| Rule ID | Attribute | Status | Notes |\n")
	sb.WriteString("|---------|-----------|--------|-------|\n")
	for _, a := range r.Required {
		notes := ""
		if a.FallbackUsed != "" {
			notes = "via `" + a.FallbackUsed + "`"
		}
		fmt.Fprintf(&sb, "| %s | `%s` | %s %s | %s |\n",
			a.RuleID, a.Attribute, statusIcon(a.Status), a.Status, notes)
	}

	sb.WriteString("\n## Optional Attributes\n\n")
	sb.WriteString("| Rule ID | Attribute | Status |\n")
	sb.WriteString("|---------|-----------|--------|\n")
	for _, a := range r.Optional {
		fmt.Fprintf(&sb, "| %s | `%s` | %s %s |\n",
			a.RuleID, a.Attribute, statusIcon(a.Status), a.Status)
	}

	return sb.String()
}

func statusIcon(status string) string {
	switch status {
	case "pass", "pass_via_fallback", "present", "present_via_fallback":
		return "✅"
	case "fail":
		return "❌"
	case "absent":
		return "⚪"
	default:
		return "❓"
	}
}

// assertNotErrorSpan fails the test if the span carries span.status_code == "error".
// The DQL filter already excludes error spans, but this catches any that slip through.
func assertNotErrorSpan(t *testing.T, span map[string]interface{}) {
	t.Helper()
	if v, ok := span["span.status_code"]; ok && fmt.Sprint(v) == "error" {
		t.Fatalf("matched an error span (span.status_code=error); check the app for failures: %v", span)
	}
}

// scopedDQL inserts a run-isolation filter immediately after the fetch statement
// (before any sort/limit) to prevent DQL from matching spans from concurrent or
// recent pipeline runs.
//
// # Isolation strategy
//
// Two branches handle the two instrumentation types in this repo:
//
//  1. OTel SDK apps (Python, Node.js, …)
//     testRunID is set once in TestMain and exported to every child process via
//     OTEL_RESOURCE_ATTRIBUTES="test.run.id=<id>". The OTel SDK merges that env
//     var into the resource automatically (Resource.create() in Python,
//     NodeSDK auto-detection in Node.js), so every span carries test.run.id as
//     a resource attribute. DQL matches on the exact value → zero cross-run
//     interference even when two pipelines run simultaneously.
//
//  2. OneAgent apps (anthropic/oneagent, openai/oneagent, aws-bedrock/oneagent)
//     OneAgent replaces the OTel TracerProvider with its own passive runtime
//     instrumentation. It does NOT read OTEL_RESOURCE_ATTRIBUTES, so test.run.id
//     is absent from those spans. The fallback branch (isNull(test.run.id) AND
//     timestamp >= suiteStartTime) provides time-based isolation instead.
//
//     Time-based isolation is sufficient here because the OneAgent DQL queries
//     already carry two narrow filters — service.name (unique per app) and
//     dt.openpipeline.source == "oneagent" — making it practically impossible
//     for a span from a different concurrent run to satisfy all filters within
//     the same time window. The CI matrix also only triggers OneAgent tests when
//     the relevant app directory changes, further reducing the chance of two
//     pipelines running the identical test at the same time.
//
// The filter is inserted after the first line (the fetch statement) so it
// evaluates before any sort or limit that the caller may have written.
func scopedDQL(dql string) string {
	filter := fmt.Sprintf(
		"| filter test.run.id == %q or (isNull(test.run.id) and timestamp >= \"%s\")\n",
		testRunID,
		suiteStartTime.UTC().Format(time.RFC3339),
	)
	// Insert after the first line (fetch statement) so the filter evaluates
	// before sort/limit, not after.
	if idx := strings.Index(dql, "\n"); idx >= 0 {
		return dql[:idx+1] + filter + dql[idx+1:]
	}
	return dql + "\n" + filter
}

// auditSpan polls DT until a span matching dql is found (5-minute timeout),
// then fetches all spans in the same trace to build a complete attribute picture.
// Writes JSON + markdown reports to test/e2e/reports/. Logs (but does NOT fail)
// any required attribute gaps. The test fails only if no anchor span is found.
// An optional note string is included in the report (e.g. to document mock backends).
func auditSpan(t *testing.T, sdk, instrumentation string, p Profile, dql string, note ...string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, scopedDQL(dql), 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
	if len(records) == 0 {
		t.Fatalf("no spans returned from DT")
	}
	assertNotErrorSpan(t, records[0])

	spans := fetchTraceSpans(t, ctx, records[0])
	report := buildReport(sdk, instrumentation, p, mergeSpans(spans))
	if len(note) > 0 {
		report.Note = note[0]
	}
	writeReport(t, report)

	for _, r := range report.Required {
		if r.Status == "fail" {
			t.Logf("required attribute missing [%s] %s", r.RuleID, r.Attribute)
		}
	}
	t.Logf("audit verdict: %s (%d spans in trace) — report written to reports/%s-%s.{json,md}",
		report.Verdict, len(spans), sdk, instrumentation)
}

// auditSpanOptional is like auditSpan but skips the (sub)test when no anchor
// span is found within the timeout instead of failing. Use for provider-specific
// audits where the provider may not have been selected in the current run.
// An optional note string is included in the report (e.g. to document mock backends).
func auditSpanOptional(t *testing.T, sdk, instrumentation string, p Profile, dql string, note ...string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, scopedDQL(dql), 15*time.Second)
	if err != nil || len(records) == 0 {
		t.Skipf("no %s/%s spans found — provider likely not selected this run", sdk, instrumentation)
		return
	}
	assertNotErrorSpan(t, records[0])

	spans := fetchTraceSpans(t, ctx, records[0])
	report := buildReport(sdk, instrumentation, p, mergeSpans(spans))
	if len(note) > 0 {
		report.Note = note[0]
	}
	writeReport(t, report)

	for _, r := range report.Required {
		if r.Status == "fail" {
			t.Logf("required attribute missing [%s] %s", r.RuleID, r.Attribute)
		}
	}
	t.Logf("audit verdict: %s (%d spans in trace) — report written to reports/%s-%s.{json,md}",
		report.Verdict, len(spans), sdk, instrumentation)
}

// fetchTraceSpans fetches all spans belonging to the same trace as anchor,
// scoped to the same service.name. Polls until the span count stabilizes
// (two consecutive equal non-zero counts) so spans that arrive in Dynatrace
// at different times are not missed. Uses a fresh 2-minute budget independent
// of the anchor-poll context.
func fetchTraceSpans(t *testing.T, _ context.Context, anchor map[string]interface{}) []map[string]interface{} {
	t.Helper()

	traceID, ok := anchor["trace.id"]
	if !ok || traceID == nil {
		t.Logf("trace.id absent in anchor span; using anchor only")
		return []map[string]interface{}{anchor}
	}
	// Strip hyphens — DQL toUid() expects a 32-char hex string.
	traceIDStr := strings.ReplaceAll(fmt.Sprint(traceID), "-", "")

	svcName := fmt.Sprint(anchor["service.name"])
	dql := fmt.Sprintf(
		"fetch spans, from: now()-10m\n| filter service.name == %q\n| filter trace.id == toUid(%q)",
		svcName, traceIDStr,
	)

	// Poll until the span count stabilizes (two consecutive equal non-zero counts).
	// Fresh 2-minute budget so anchor-poll time does not reduce this window.
	stableCtx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	lastCount := -1
	var lastSpans []map[string]interface{}

	for {
		spans, err := dtClient.Execute(stableCtx, dql)
		if err != nil {
			t.Logf("warning: fetch trace spans: %v; using anchor only", err)
			return []map[string]interface{}{anchor}
		}

		if len(spans) > 0 && len(spans) == lastCount {
			t.Logf("trace spans stabilized at %d", len(spans))
			return spans
		}
		lastCount = len(spans)
		lastSpans = spans

		select {
		case <-stableCtx.Done():
			if len(lastSpans) > 0 {
				t.Logf("warning: trace span count did not stabilize within timeout; using %d spans", len(lastSpans))
				return lastSpans
			}
			return []map[string]interface{}{anchor}
		case <-time.After(15 * time.Second):
		}
	}
}

// mergeSpans folds multiple span records into one map: for each attribute, the
// first non-empty value across all spans wins. This lets a single evaluateCheck
// call see attributes spread across different spans of the same trace.
func mergeSpans(spans []map[string]interface{}) map[string]interface{} {
	merged := make(map[string]interface{})
	for _, span := range spans {
		for k, v := range span {
			if _, exists := merged[k]; !exists && v != nil && fmt.Sprint(v) != "" {
				merged[k] = v
			}
		}
	}
	return merged
}
