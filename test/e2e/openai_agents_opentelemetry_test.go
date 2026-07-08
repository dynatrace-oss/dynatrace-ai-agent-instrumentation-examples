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
| filter gen_ai.provider.name == "azure.ai.openai" or gen_ai.system == "azure.ai.openai"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
