package e2e

import (
	"testing"
)

func TestCohereOpenInference(t *testing.T) {
	startCohereCompatibleMock(t)
	startApp(t, "cohere/openinference")
	triggerHaiku(t, true)

	auditSpanWithMetrics(t, "cohere", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "cohere/openinference"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"cohere/openinference", genAIClientMetrics,
		"Backend mocked: in-process httptest stub intercepts Cohere SDK calls via CO_API_URL. Replace with a real COHERE_API_KEY secret for live validation.")
}
