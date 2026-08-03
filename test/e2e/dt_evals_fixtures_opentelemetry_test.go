package e2e

import (
	"testing"
)

// TestDtEvalsFixturesOpenTelemetry starts the dt-evals fixtures app, replays every
// deterministic fixture via POST /ingest, and audits that the resulting GenAI
// spans reach the tenant under service.name == "dt-evals-fixtures". Unlike the
// LLM-backed suites the content is canned, so the spans are identical every run.
//
// It also asserts the two GenAI client metrics. The app sets
// should_enrich_metrics=True + delta temporality and exports OTLP directly to the
// tenant (no collector), so this doubles as the verification that the metric
// pipeline works over direct OTLP — if the metrics do not arrive, this fails.
//
// Note: the effective service.name comes from fixtures.json (Traceloop app_name),
// not the matrix OTEL_SERVICE_NAME — the DQL filter and metric lookup must match it.
func TestDtEvalsFixturesOpenTelemetry(t *testing.T) {
	startApp(t, "dt-evals-fixtures/opentelemetry")
	triggerIngest(t)

	auditSpanWithMetrics(t, "dt-evals-fixtures", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "dt-evals-fixtures"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`,
		"dt-evals-fixtures", genAIClientMetrics,
		"Deterministic fixture replayer: should_enrich_metrics=True + delta temporality, direct OTLP to the tenant (no collector).")
}
