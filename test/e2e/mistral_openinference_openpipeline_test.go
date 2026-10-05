package e2e

import "testing"

func TestMistralOpenInferenceOpenPipeline(t *testing.T) {
	startMistralCompatibleMock(t)

	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no
	// collector). Attribute transformation happens server-side via the
	// OpenPipeline mistral-openinference-ai-spans pipeline, which must be
	// deployed in the tenant first (see mistral/openinference/README.md, Option B).
	startCLIAppWithTarget(t, "mistral/openinference", "run-openpipeline")

	// service.name == "mistral/openinference-openpipeline" keeps this data set
	// distinct from the collector-based test (service.name == "mistral/openinference").
	auditSpanWithMetrics(t, "mistral", "openinference-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "mistral/openinference-openpipeline"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"mistral/openinference-openpipeline", genAIClientMetrics,
		"Backend mocked: a local HTTP stub serves Mistral-compatible chat completions via MISTRAL_BASE_URL. Requires the mistral-openinference-ai-spans OpenPipeline pipeline to be deployed in the tenant.")
}
