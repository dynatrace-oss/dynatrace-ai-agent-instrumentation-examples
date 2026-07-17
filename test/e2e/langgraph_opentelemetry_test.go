package e2e

import (
	"testing"
)

func TestLangGraphOpenTelemetry(t *testing.T) {
	startApp(t, "langgraph/opentelemetry")
	triggerHaiku(t, false)

	auditSpan(t, "langgraph", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langgraph"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
