package e2e

import (
	"testing"
)

func TestGroqOneAgent(t *testing.T) {
	startOpenAICompatibleMock(t, "GROQ_API_KEY", "GROQ_BASE_URL")
	startApp(t, "groq/oneagent")
	triggerHaiku(t, false)

	auditSpan(t, "groq", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "groq/oneagent"
| filter gen_ai.provider.name == "groq"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
