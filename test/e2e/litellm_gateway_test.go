package e2e

import (
	"testing"
)

func TestLiteLLMOpenTelemetryGateway(t *testing.T) {
	startApp(t, "litellm/opentelemetry/litellm-gateway-with-instrumentation")
	triggerLiteLLMChat(t)

	// OpenInference emits spans only (no GenAI client metrics), so this audits spans alone.
	auditSpan(t, "litellm", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "litellm-gateway"
| filter isNull(span.status_code) or span.status_code != "error"
| filter isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)
| limit 1`)
}
