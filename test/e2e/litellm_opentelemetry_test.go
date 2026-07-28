package e2e

import (
	"testing"
)

func TestLiteLLMOpenTelemetry(t *testing.T) {
	startApp(t, "litellm/opentelemetry")
	triggerLiteLLMChat(t)

	// Traceloop emits the OTel GenAI client metrics; delta temporality and the
	// insecure gRPC exporters (added in the app entry points) are required for
	// them to reach Dynatrace. Metric results are recorded in the generated report.
	auditSpanWithMetrics(t, "litellm", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "litellm-gateway"
| filter isNull(span.status_code) or span.status_code != "error"
| filter isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)
| limit 1`,
		"litellm-gateway", genAIClientMetrics)
}
