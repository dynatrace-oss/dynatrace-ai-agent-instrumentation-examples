package e2e

import (
	"testing"
)

func TestMicrosoftAgentFrameworkOpenTelemetry(t *testing.T) {
	startCLIApp(t, "microsoft-agent-framework/opentelemetry")

	auditSpan(t, "microsoft-agent-framework", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "microsoft-agent-framework"
| filter gen_ai.provider.name == "microsoft.agent_framework"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
