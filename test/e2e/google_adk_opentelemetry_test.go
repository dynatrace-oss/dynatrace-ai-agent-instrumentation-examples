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
}
