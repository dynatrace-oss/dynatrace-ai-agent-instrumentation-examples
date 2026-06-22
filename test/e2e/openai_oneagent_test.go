package e2e

import (
	"testing"
)

func TestOpenAIOneAgent(t *testing.T) {
	startApp(t, "openai/oneagent")
	triggerHaiku(t, false)

	auditSpan(t, "openai", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
