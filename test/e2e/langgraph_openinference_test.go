package e2e

import (
	"testing"
)

func TestLangGraphOpenInference(t *testing.T) {
	startApp(t, "langgraph/openinference")
	makeRequest(t, "langgraph/openinference", "request")

	auditSpanWithMetrics(t, "langgraph", "openinference", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langgraph/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"langgraph/openinference", genAIClientMetrics)
}
