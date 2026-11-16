package e2e

import (
	"testing"
	"time"
)

func TestGeminiOpenInference(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once
	// against the real Gemini API (GOOGLE_API_KEY). app.py sends two turns of
	// one conversation, each in its own trace.
	startCLIApp(t, "gemini/openinference")

	auditSpanWithMetrics(t, "gemini", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "gemini/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"gemini/openinference", genAIClientMetrics)

	// Both turns share one conversation id but land in separate traces.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "gemini/openinference"
| filter isNotNull(gen_ai.conversation.id)
| summarize traces = countDistinct(trace.id), by: {gen_ai.conversation.id}
| filter traces >= 2
| limit 1`), 5*time.Minute)
}
