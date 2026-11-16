package e2e

import (
	"testing"
)

func TestGroqOpenInference(t *testing.T) {
	startOpenAICompatibleMock(t, "GROQ_API_KEY", "GROQ_BASE_URL")
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startCLIApp(t, "groq/openinference")

	auditSpanWithMetrics(t, "groq", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "groq/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"groq/openinference", genAIClientMetrics,
		"Backend mocked: a local HTTP stub serves Groq-compatible chat completions via GROQ_BASE_URL. Replace with a real GROQ_API_KEY secret for live validation.")
}
