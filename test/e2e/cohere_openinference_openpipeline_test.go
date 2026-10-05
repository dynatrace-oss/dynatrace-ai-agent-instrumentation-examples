package e2e

import "testing"

func TestCohereOpenInferenceOpenPipeline(t *testing.T) {
	startCohereCompatibleMock(t)

	// HTTP app: make run-openpipeline sends spans directly to Dynatrace (no
	// collector). Attribute transformation happens server-side via the
	// OpenPipeline cohere-openinference-ai-spans pipeline, which must be
	// deployed in the tenant first (see cohere/openinference/README.md, Option B).
	startAppWithTarget(t, "cohere/openinference", "run-openpipeline")
	triggerHaiku(t, true)

	// service.name == "cohere/openinference-openpipeline" keeps this data set
	// distinct from the collector-based test (service.name == "cohere/openinference").
	auditSpanWithMetrics(t, "cohere", "openinference-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "cohere/openinference-openpipeline"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"cohere/openinference-openpipeline", genAIClientMetrics,
		"Backend mocked: in-process httptest stub intercepts Cohere SDK calls via CO_API_URL. Requires the cohere-openinference-ai-spans OpenPipeline pipeline to be deployed in the tenant.")
}
