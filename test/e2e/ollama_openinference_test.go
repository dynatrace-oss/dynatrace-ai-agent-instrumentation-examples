package e2e

import (
	"testing"
)

func TestOllamaOpenInference(t *testing.T) {
	startApp(t, "ollama/openinference")
	triggerHaiku(t, true)

	auditSpanWithMetrics(t, "ollama", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "ollama/openinference"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"ollama/openinference", genAIClientMetrics)
}
