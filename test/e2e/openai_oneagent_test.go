package e2e

import (
	"testing"
)

func TestOpenAIOneAgent(t *testing.T) {
	startApp(t, "openai/oneagent")
	triggerHaiku(t, false)

	auditSpan(t, "openai", "oneagent", OpenAIProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
