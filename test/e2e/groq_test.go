package e2e

import (
	"testing"
)

func TestGroqOneAgent(t *testing.T) {
	startOpenAICompatibleMock(t, "GROQ_API_KEY", "GROQ_BASE_URL")
	startApp(t, "groq/oneagent")
	triggerHaiku(t, false)

	// TODO: confirm gen_ai.system / gen_ai.provider.name emitted by OneAgent
	// for the Groq SDK and tighten the provider filter once span metadata is known.
	auditSpan(t, "groq", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "groq/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
