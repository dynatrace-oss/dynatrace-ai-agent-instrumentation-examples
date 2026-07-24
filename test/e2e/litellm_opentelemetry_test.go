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
| filter isNull(span.status_code) or span.status_code != "error"
| filter isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)
| limit 1`)

	// Traceloop emits the OTel GenAI client metrics; delta temporality (added in
	// the app entry points) is required for Dynatrace to accept them.
	assertGenAIClientMetrics(t, "litellm-gateway")
}
