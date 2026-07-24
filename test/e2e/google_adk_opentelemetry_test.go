package e2e

import (
	"testing"
)

func TestGoogleADKOpenTelemetry(t *testing.T) {
	startApp(t, "google-adk/opentelemetry")
	triggerResearch(t)

	auditSpan(t, "google-adk", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk-samples"
| filter gen_ai.system == "gemini"
| sort timestamp desc
| limit 1`)

	// Google ADK records the OTel GenAI client metrics natively; the MeterProvider
	// + delta temporality added in app.py are required to export and accept them.
	assertGenAIClientMetrics(t, "google-adk-samples")
}
