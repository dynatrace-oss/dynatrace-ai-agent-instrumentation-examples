package e2e

import (
	"testing"
)

func TestGeminiOpenInference(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once
	// against the real Gemini API (GOOGLE_API_KEY).
	startCLIApp(t, "gemini/openinference")

	auditSpanWithMetrics(t, "gemini", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "gemini/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"gemini/openinference", genAIClientMetrics)
}
