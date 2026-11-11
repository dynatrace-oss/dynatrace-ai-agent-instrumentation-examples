package e2e

import (
	"testing"
	"time"
)

func TestGroqOneAgent(t *testing.T) {
	startOpenAICompatibleMock(t, "GROQ_API_KEY", "GROQ_BASE_URL")
	startApp(t, "groq/oneagent")
	triggerHaiku(t, false)

	// Requires the opt-in OneAgent prompt capture feature for this sensor.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "groq/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.input.messages) and isNotNull(gen_ai.output.messages)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	auditSpan(t, "groq", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "groq/oneagent"
| filter gen_ai.provider.name == "groq" or gen_ai.system == "groq"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"Backend mocked: ollama running tinyllama locally serves Groq-compatible requests via GROQ_BASE_URL. Replace with a real GROQ_API_KEY secret for live validation.")
}
