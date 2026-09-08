package e2e

import "testing"

func TestHaystackOpenInferenceOpenPipeline(t *testing.T) {
	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no
	// collector). Attribute transformation happens server-side via the
	// OpenPipeline haystack-openinference-ai-spans pipeline, which must be
	// deployed in the tenant first (see haystack/openinference/README.md, Option B).
	startCLIAppWithTarget(t, "haystack/openinference", "run-openpipeline")

	// service.name == "haystack/openinference-openpipeline" keeps this data set
	// distinct from the collector-based test (service.name == "haystack/openinference").
	auditSpanWithMetrics(t, "haystack", "openinference-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "haystack/openinference-openpipeline"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"haystack/openinference-openpipeline", genAIClientMetrics)
}
