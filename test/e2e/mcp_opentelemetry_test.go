package e2e

import (
	"testing"
)

func TestMCPOpenTelemetry(t *testing.T) {
	startApp(t, "mcp/opentelemetry")
	triggerMCPAgent(t)

	auditSpan(t, "mcp", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "mcp-agent-demo"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
