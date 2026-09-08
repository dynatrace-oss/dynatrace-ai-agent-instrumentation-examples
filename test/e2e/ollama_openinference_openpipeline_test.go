package e2e

import "testing"

func TestOllamaOpenInferenceOpenPipeline(t *testing.T) {
	// HTTP app: make run-openpipeline sends spans directly to Dynatrace (no
	// collector). Attribute transformation happens server-side via the
	// OpenPipeline ollama-openinference-ai-spans pipeline, which must be
	// deployed in the tenant first (see ollama/openinference/README.md, Option B).
	startAppWithTarget(t, "ollama/openinference", "run-openpipeline")
	triggerHaiku(t, true)

	// service.name == "ollama/openinference-openpipeline" keeps this data set
	// distinct from the collector-based test (service.name == "ollama/openinference").
	auditSpanWithMetrics(t, "ollama", "openinference-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "ollama/openinference-openpipeline"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"ollama/openinference-openpipeline", genAIClientMetrics,
		"Requires the ollama-openinference-ai-spans OpenPipeline pipeline to be deployed in the tenant.")
}
