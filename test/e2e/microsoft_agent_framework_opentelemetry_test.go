package e2e

import (
	"testing"
)

func TestMicrosoftAgentFrameworkOpenTelemetry(t *testing.T) {
	startCLIApp(t, "microsoft-agent-framework/opentelemetry")

	auditSpan(t, "microsoft-agent-framework", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "microsoft-agent-framework"
| filter isNotNull(gen_ai.system)
| limit 1`)
}
