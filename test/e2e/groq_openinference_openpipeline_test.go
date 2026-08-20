package e2e

import "testing"

func TestGroqOpenInferenceOpenPipeline(t *testing.T) {
	startOpenAICompatibleMock(t, "GROQ_API_KEY", "GROQ_BASE_URL")

	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no
	// collector). Attribute transformation happens server-side via the
	// OpenPipeline groq-openinference-ai-spans pipeline, which must be
	// deployed in the tenant first (see groq/openinference/README.md, Option B).
	startCLIAppWithTarget(t, "groq/openinference", "run-openpipeline")

	// service.name == "groq/openinference-openpipeline" keeps this data set
	// distinct from the collector-based test (service.name == "groq/openinference").
	auditSpanWithMetrics(t, "groq", "openinference-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "groq/openinference-openpipeline"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"groq/openinference-openpipeline", genAIClientMetrics,
		"Backend mocked: a local HTTP stub serves Groq-compatible chat completions via GROQ_BASE_URL. Requires the groq-openinference-ai-spans OpenPipeline pipeline to be deployed in the tenant.")
}
