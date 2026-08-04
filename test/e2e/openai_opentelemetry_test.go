package e2e

import (
	"testing"
)

func TestOpenAIOpenTelemetry(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startCLIApp(t, "openai/opentelemetry")

	auditSpan(t, "openai", "opentelemetry", OpenAIProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
