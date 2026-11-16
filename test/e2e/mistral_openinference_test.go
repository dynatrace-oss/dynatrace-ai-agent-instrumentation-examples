package e2e

import (
	"testing"
)

func TestMistralOpenInference(t *testing.T) {
	startMistralCompatibleMock(t)
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startCLIApp(t, "mistral/openinference")

	auditSpanWithMetrics(t, "mistral", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "mistral/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"mistral/openinference", genAIClientMetrics,
		"Backend mocked: a local HTTP stub serves Mistral-compatible chat completions via MISTRAL_BASE_URL. Replace with a real MISTRAL_API_KEY secret for live validation.")
}
