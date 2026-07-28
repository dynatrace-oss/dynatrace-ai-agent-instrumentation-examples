package e2e

import (
	"testing"
)

func TestOpenAIOneAgent(t *testing.T) {
	startApp(t, "openai/oneagent")
	triggerHaiku(t, false)

	auditSpanWithMetrics(t, "openai", "oneagent", OpenAIProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"openai/oneagent", genAIClientMetrics)
}
