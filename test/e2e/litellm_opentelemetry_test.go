package e2e

import (
	"testing"
)

func TestLiteLLMOpenTelemetry(t *testing.T) {
	startApp(t, "litellm/opentelemetry/fastapi-instrumentation")
	triggerLiteLLMChat(t)

	// OpenInference emits spans only; the Collector derives the gen_ai.client.* metrics from them.
	auditSpanWithMetrics(t, "litellm", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "litellm-gateway-fastapi"
| filter isNull(span.status_code) or span.status_code != "error"
| filter isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)
| limit 1`,
		"litellm-gateway-fastapi", genAIClientMetrics)
}
