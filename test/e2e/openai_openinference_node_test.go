package e2e

import (
	"os"
	"testing"
)

func TestOpenAIOpenInferenceNode(t *testing.T) {
	if os.Getenv("MODEL") == "" {
		t.Setenv("MODEL", "gpt-4o-mini")
	}
	startOpenAICompatibleMock(t, "OPENAI_API_KEY", "OPENAI_API_BASE")
	startApp(t, "openai/openinference/node")
	triggerHaiku(t, true)

	auditSpanWithMetrics(t, "openai", "openinference-node", OpenAIProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/openinference/node"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"openai/openinference/node", genAIClientMetrics)
}
