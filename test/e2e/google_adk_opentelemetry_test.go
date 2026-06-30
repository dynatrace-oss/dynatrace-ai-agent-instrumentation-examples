package e2e

import (
	"testing"
)

func TestGoogleADKOpenTelemetry(t *testing.T) {
	startApp(t, "google-adk/opentelemetry")
	triggerHaiku(t, true)

	auditSpan(t, "google-adk", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk-samples"
| filter isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`)
}
