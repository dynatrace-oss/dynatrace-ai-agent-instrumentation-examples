package e2e

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// genAIClientMetrics are the two core OTel GenAI client metrics the AI
// Observability app charts (cost and latency).
var genAIClientMetrics = []string{
	"gen_ai.client.token.usage",
	"gen_ai.client.operation.duration",
}

// pollMetricExists polls Dynatrace until the given OTel metric has at least one
// non-zero data point for the service, or the 5-minute timeout elapses. It
// returns whether the metric was found.
//
// Query errors (e.g. the metric key not yet ingested early in the run) are
// treated as retryable rather than fatal, so the check waits for the first data
// points. Isolation is time-based: OTLP metric data points do not carry
// test.run.id as a dimension, so the window is anchored at suiteStartTime to
// exclude earlier runs. Combined with a unique service.name this is sufficient
// for an existence check. Metrics are exported on a periodic reader interval, so
// the first data points can lag spans by up to ~60s — the budget absorbs that.
func pollMetricExists(t *testing.T, serviceName, metricKey string) bool {
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

	for {
		records, err := dtClient.Execute(ctx, dql)
		if err == nil && len(records) > 0 {
			return true
		}
		select {
		case <-ctx.Done():
			return false
		case <-time.After(15 * time.Second):
		}
	}
}

// auditSpanWithMetrics runs the span audit and additionally checks that each
// metric in metricKeys exists for serviceName, recording every result in the
// same report (written to test/e2e/reports/). A missing metric fails the test
// (via Errorf) but does not abort before the report is written, so the report
// always reflects the full outcome.
func auditSpanWithMetrics(t *testing.T, sdk, instrumentation string, p Profile, dql, serviceName string, metricKeys []string, note ...string) {
	t.Helper()
	report, spanCount := buildSpanReport(t, sdk, instrumentation, p, dql, note...)

	for _, key := range metricKeys {
		status := "absent"
		if pollMetricExists(t, serviceName, key) {
			status = "present"
		} else {
			t.Errorf("metric %q not found for service %q within timeout", key, serviceName)
		}
		report.Metrics = append(report.Metrics, MetricResult{Metric: key, Status: status})
	}

	writeReport(t, report)
	logAuditResult(t, report, spanCount)
}
