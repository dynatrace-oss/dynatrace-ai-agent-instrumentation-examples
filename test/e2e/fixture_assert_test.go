package e2e

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// assertSpanExists polls DT until at least one span matching dql is found
// (3-minute timeout). Use this when the relevant attribute cannot be asserted
// (e.g. instrumentation libraries that don't emit gen_ai.system).
func assertSpanExists(t *testing.T, dql string) {
	t.Helper()
	assertSpanExistsWithin(t, dql, 3*time.Minute)
}

// assertSpanExistsWithin is assertSpanExists with a caller-chosen timeout. Use a
// longer timeout for OneAgent-captured spans: their fullstack ingestion into
// Grail lags further behind the request than the OTLP path, so the default
// 3-minute window is prone to flaking on the first span of a OneAgent run.
func assertSpanExistsWithin(t *testing.T, dql string, timeout time.Duration) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	_, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
}

// assertGenAIDurationMetric polls DT until the gen_ai.client.operation.duration
// metric reports data for the given service (5-minute timeout), failing the test
// otherwise. This is the metric the AI Observability app charts
// (timeseries avg(gen_ai.client.operation.duration)); the OTel Collector path
// gets it from the built-in span pipeline, and the OpenPipeline path from the
// samplingAwareHistogramMetric processor in openpipeline-langfuse.yaml.
//
// Scoping matches the app's service filter — coalesce(service.name,
// getNodeName(dt.smartscape.service)) — since extracted metrics carry no
// test.run.id dimension and cannot be run-isolated. The 20-minute lookback and
// 5-minute poll allow for metric aggregation lag, which is longer than for spans.
func assertGenAIDurationMetric(t *testing.T, service string) {
	t.Helper()
	// The service filter must be a parameter of the timeseries command (where the
	// metric's dimensions are in scope), not a downstream pipe stage (where only
	// duration/timeframe/interval exist). Mirrors the app's toTimeseriesFilterString().
	dql := fmt.Sprintf(
		`timeseries duration = avg(gen_ai.client.operation.duration), from: now()-20m, filter: matchesValue(coalesce(service.name, getNodeName(dt.smartscape.service)), %q)
| fieldsAdd total = arraySum(duration)
| filter isNotNull(total) and total > 0`,
		service,
	)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT metric gen_ai.client.operation.duration for %q: %v", service, err)
	}
	if len(records) == 0 {
		t.Fatalf("metric gen_ai.client.operation.duration reported no data for service %q", service)
	}
	t.Logf("metric gen_ai.client.operation.duration present for service %q", service)
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

// assertGenAISpan polls DT until a span matching dql is found (3-minute
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
