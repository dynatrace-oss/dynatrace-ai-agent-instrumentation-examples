package e2e

import "testing"

func TestTogetherOpenInferenceOpenPipeline(t *testing.T) {
	startOpenAICompatibleMock(t, "TOGETHER_API_KEY", "TOGETHER_BASE_URL")

	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no
	// collector). Attribute transformation happens server-side via the
	// OpenPipeline together-openinference-ai-spans pipeline, which must be
	// deployed in the tenant first (see together/openinference/README.md, Option B).
	startCLIAppWithTarget(t, "together/openinference", "run-openpipeline")

	// service.name == "together/openinference-openpipeline" keeps this data set
	// distinct from the collector-based test (service.name == "together/openinference").
	auditSpanWithMetrics(t, "together", "openinference-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "together/openinference-openpipeline"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"together/openinference-openpipeline", genAIClientMetrics,
		"Backend mocked: a local HTTP stub serves Together AI-compatible chat completions via TOGETHER_BASE_URL. Requires the together-openinference-ai-spans OpenPipeline pipeline to be deployed in the tenant.")
}
