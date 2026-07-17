package e2e

import (
	"context"
	"testing"
	"time"
)

// assertSpanExists polls DT until at least one span matching dql is found
// (3-minute timeout). Use this when the relevant attribute cannot be asserted
// (e.g. instrumentation libraries that don't emit gen_ai.system).
func assertSpanExists(t *testing.T, dql string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	_, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
}

// assertSpanWithAttrs polls DT until a span matching dql is found (3-minute
// timeout), then asserts that every attribute in required is non-null, and that
// at least one attribute in each anyOf group is non-null.
func assertSpanWithAttrs(t *testing.T, dql string, required []string, anyOf [][]string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
	if len(records) == 0 {
		t.Fatal("no spans returned from DT")
	}

	span := records[0]
	for _, attr := range required {
		v, ok := span[attr]
		if !ok || v == nil || v == "" {
			t.Errorf("span missing required attribute %q", attr)
		}
	}
	for _, group := range anyOf {
		found := false
		for _, attr := range group {
			if v, ok := span[attr]; ok && v != nil && v != "" {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("span missing at least one of %v", group)
		}
	}
}

// assertNoMatchingSpan fails the test if any span matching dql appears within
// 45 seconds. It re-polls every 15s so a span still in-flight cannot slip
// through after its redacted sibling becomes visible.
func assertNoMatchingSpan(t *testing.T, dql string) {
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


// timeout), then asserts gen_ai.system equals wantSystem.
func assertGenAISpan(t *testing.T, dql, wantSystem string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
	if len(records) == 0 {
		t.Fatal("no spans returned from DT")
	}

	span := records[0]
	system, ok := span["gen_ai.provider.name"]
	if !ok {
		system, ok = span["gen_ai.system"]
	}
	if !ok {
		t.Fatal("span missing gen_ai.provider.name and gen_ai.system")
	}
	if system != wantSystem {
		t.Errorf("gen_ai.provider.name/gen_ai.system = %q, want %q", system, wantSystem)
	}
}
