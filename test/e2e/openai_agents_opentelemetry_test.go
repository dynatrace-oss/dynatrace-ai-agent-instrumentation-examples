package e2e

import (
	"testing"
)

func TestOpenAIAgentsOpenTelemetry(t *testing.T) {
	startApp(t, "openai-agents/opentelemetry")
	triggerCSAgent(t)

	auditSpan(t, "openai-agents", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai-cs-agents"
| filter gen_ai.system == "openai"
| limit 1`)
}
