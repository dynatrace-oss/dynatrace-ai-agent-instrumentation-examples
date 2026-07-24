package e2e

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// assertMetricExists polls Dynatrace until the given OTel metric has at least one
// non-zero data point for the service, or fails after a 5-minute timeout.
//
// It applies the same poll-until-present approach auditSpan uses for spans, but
// queries the metric store via timeseries instead of fetching spans. Query errors
// (e.g. the metric key not yet ingested early in the run) are treated as
// retryable rather than fatal, so the assertion waits for the first data points.
//
// Isolation is time-based: OTLP metric data points do not carry test.run.id as a
// dimension, so the window is anchored at suiteStartTime to exclude earlier runs.
// Combined with a unique service.name this is sufficient for an existence check.
// Metrics are exported on a periodic reader interval, so the first data points can
// lag spans by up to ~60s — the 5-minute budget absorbs that.
func assertMetricExists(t *testing.T, serviceName, metricKey string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	from := fmt.Sprintf("%q", suiteStartTime.UTC().Format(time.RFC3339))
	dql := fmt.Sprintf(
		"timeseries val = sum(%s), by:{ service.name }, from: %s\n"+
			"| filter service.name == %q\n"+
			"| filter arraySum(val) > 0",
		metricKey, from, serviceName,
	)

	var lastErr error
	for {
		records, err := dtClient.Execute(ctx, dql)
		if err == nil && len(records) > 0 {
			t.Logf("metric %q present for service %q", metricKey, serviceName)
			return
		}
		if err != nil {
			// Early in the run the metric key may not be ingested yet; keep polling.
			lastErr = err
		}
		select {
		case <-ctx.Done():
			if lastErr != nil {
				t.Fatalf("metric %q not found for service %q within timeout (last query error: %v)",
					metricKey, serviceName, lastErr)
			}
			t.Fatalf("metric %q not found for service %q within timeout", metricKey, serviceName)
		case <-time.After(15 * time.Second):
		}
	}
}

// assertGenAIClientMetrics asserts that both core OTel GenAI client metrics are
// present for a service. Use for examples whose instrumentation emits the semconv
// metrics (gen_ai.client.token.usage, gen_ai.client.operation.duration) once
// delta temporality and a metric exporter are configured.
func assertGenAIClientMetrics(t *testing.T, serviceName string) {
	t.Helper()
	t.Run("metric gen_ai.client.token.usage", func(t *testing.T) {
		assertMetricExists(t, serviceName, "gen_ai.client.token.usage")
	})
	t.Run("metric gen_ai.client.operation.duration", func(t *testing.T) {
		assertMetricExists(t, serviceName, "gen_ai.client.operation.duration")
	})
}
