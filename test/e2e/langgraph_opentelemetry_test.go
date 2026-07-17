package e2e

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"testing"
	"time"
)

// triggerHaikuTopic POSTs /haiku on localhost:8000 with a specific topic so the
// captured input message content is controllable per request.
func triggerHaikuTopic(t *testing.T, topic string) {
	t.Helper()
	b, _ := json.Marshal(map[string]string{"topic": topic})
	resp, err := http.Post("http://127.0.0.1:8000/haiku", "application/json", bytes.NewReader(b))
	if err != nil {
		t.Fatalf("POST /haiku (%q): %v", topic, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /haiku (%q) returned %d: %s", topic, resp.StatusCode, body)
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

	triggerHaikuTopic(t, "the secret launch codes")
	triggerHaikuTopic(t, "cherry blossoms in spring")

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
