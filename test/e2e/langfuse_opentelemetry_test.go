package e2e

import (
	"testing"
)

func TestLangfuseOpenTelemetry(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startCLIApp(t, "langfuse/opentelemetry")

	auditSpan(t, "langfuse", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langfuse"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
