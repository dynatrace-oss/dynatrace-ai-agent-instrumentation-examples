package e2e

import (
	"testing"
)

func TestOpenAIOpenInference(t *testing.T) {
	startApp(t, "openai/openinference")
	triggerHaiku(t, "openinference")
	auditSpanWithMetrics(t, "openai", "openinference", OpenAIProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"openai/openinference", genAIClientMetrics)
}
