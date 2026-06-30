package e2e

import (
	"testing"
)

func TestCrewAIOpenTelemetry(t *testing.T) {
	startApp(t, "crewai/opentelemetry")
	triggerHaiku(t, false)

	auditSpan(t, "crewai", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "crewai"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
