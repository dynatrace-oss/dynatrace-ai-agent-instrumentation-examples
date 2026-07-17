package e2e

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

// makeRequest runs a request target from the demo's Makefile (e.g. "request"
// or "request-secret"), keeping the secret/non-secret topics defined in one
// place — the Makefile.
func makeRequest(t *testing.T, appDir, target string) {
	t.Helper()
	cmd := exec.Command("make", "-C", filepath.Join(repoRoot(), appDir), target)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		t.Fatalf("make %s in %s: %v", target, appDir, err)
	}
}

// assertNoSpan fails if any span matches dql. It re-checks for 45s to guard
// against a span that is still in flight (the redaction happens in the
// collector, so a leaked secret would already be ingested by the time its
// redacted sibling span is visible).
func assertNoSpan(t *testing.T, dql string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	for {
		records, err := dtClient.Execute(ctx, dql)
		if err != nil {
			t.Fatalf("query DT spans: %v", err)
		}
		if len(records) > 0 {
			t.Fatalf("expected no spans for query, got %d: %v", len(records), records[0])
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(15 * time.Second):
		}
	}
}

// TestLangGraphOpenTelemetry exercises the LangGraph demo through a Dynatrace
// OpenTelemetry Collector that anonymizes input messages mentioning "secret".
// It sends two requests — one whose topic contains "secret" and one that does
// not — and asserts the first is redacted while the second passes through.
func TestLangGraphOpenTelemetry(t *testing.T) {
	startApp(t, "langgraph/opentelemetry")

	// Drive both paths via the Makefile: request-secret sends a "secret" topic
	// (redacted by the collector); request sends a benign one (passes through).
	makeRequest(t, "langgraph/opentelemetry", "request-secret")
	makeRequest(t, "langgraph/opentelemetry", "request")

	// The secret-bearing input message must be redacted by the collector.
	assertSpanExists(t, scopedDQL(`fetch spans
| filter service.name == "langgraph"
| filter `+"`gen_ai.input.messages`"+` == "***REDACTED***"
| sort timestamp desc
| limit 1`))

	// The non-secret input message must reach Dynatrace unmodified.
	assertSpanExists(t, scopedDQL(`fetch spans
| filter service.name == "langgraph"
| filter contains(`+"`gen_ai.input.messages`"+`, "cherry blossoms")
| sort timestamp desc
| limit 1`))

	// The secret content must never be ingested in any form.
	assertNoSpan(t, scopedDQL(`fetch spans
| filter service.name == "langgraph"
| filter contains(`+"`gen_ai.input.messages`"+`, "launch codes")
| limit 1`))

	auditSpan(t, "langgraph", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langgraph"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
