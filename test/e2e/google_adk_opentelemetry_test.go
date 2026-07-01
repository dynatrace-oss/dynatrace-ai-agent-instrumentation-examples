package e2e

import (
	"fmt"
	"testing"
	"time"
)

func TestGoogleADKOpenTelemetry(t *testing.T) {
	runID := fmt.Sprintf("%d", time.Now().UnixNano())
	t.Setenv("OTEL_RESOURCE_ATTRIBUTES", "test.run.id="+runID)

	startApp(t, "google-adk/opentelemetry")
	triggerResearch(t)

	auditSpan(t, "google-adk", "opentelemetry", GenericProfile,
		fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == "google-adk-samples"
| filter test.run.id == "%s"
| filter gen_ai.system == "gemini"
| sort timestamp desc
| limit 1`, runID))
}
