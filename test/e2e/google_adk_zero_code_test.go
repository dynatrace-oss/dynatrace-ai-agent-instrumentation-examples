package e2e

import (
	"testing"
)

func TestGoogleADKZeroCode(t *testing.T) {
	// Same agent as google-adk/opentelemetry, with no OTel code in the app:
	// opentelemetry-instrument builds the providers from OTEL_* env vars before
	// app.py is imported. The audit therefore verifies that env-only
	// configuration reaches the same attribute coverage as the in-code variant.
	//
	// Exports straight to Dynatrace, no collector. Two consequences:
	//   - AR-005 (gen_ai.response.model) is reported as a gap. ADK records the
	//     response model only as a metric attribute, never on a span, so no
	//     configuration in this demo can close it. Same reason the direct-export
	//     variant of the collector suite was dropped.
	//   - The derived gen_ai.invoke_agent.duration / gen_ai.execute_tool.duration
	//     metrics are absent; those come from the collector's span_metrics
	//     connector, which this demo deliberately does not run.
	startApp(t, "google-adk/zero-code")
	triggerResearch(t)

	auditSpanWithMetrics(t, "google-adk", "zero-code", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk-zero-code"
| filter gen_ai.provider.name == "gemini"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"google-adk-zero-code", genAIClientMetrics)

	// ADK's own spans are all span.kind=internal, so no service is detected in
	// SDv2 without an entry-point instrumentation. The FastAPI instrumentation,
	// loaded by opentelemetry-instrument, is what produces the SERVER span.
	assertSpanExists(t, `fetch spans, from: now()-10m
| filter service.name == "google-adk-zero-code"
| filter span.kind == "server"
| limit 1`)
}
