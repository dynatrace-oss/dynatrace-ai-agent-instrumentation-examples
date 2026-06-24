package e2e

import (
	"testing"
)

func TestLiteLLMOpenTelemetry(t *testing.T) {
	startApp(t, "litellm/opentelemetry")
	triggerLiteLLMChat(t)

	auditSpan(t, "litellm", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "litellm-gateway"
| filter isNotNull(gen_ai.system)
| limit 1`)
}
