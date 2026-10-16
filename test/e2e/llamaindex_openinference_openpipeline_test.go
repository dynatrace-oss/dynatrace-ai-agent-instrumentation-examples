package e2e

import "testing"

func TestLlamaIndexOpenInferenceOpenPipeline(t *testing.T) {
	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no
	// collector). Spans carry gen_ai.* natively; the OpenPipeline
	// llamaindex-openinference-ai-spans pipeline only derives metrics and must be
	// deployed in the tenant first (see llamaindex/openinference/README.md, Option B).
	startCLIAppWithTarget(t, "llamaindex/openinference", "run-openpipeline")

	// service.name == "llamaindex/openinference-openpipeline" keeps this data set
	// distinct from the collector-based test (service.name == "llamaindex/openinference").
	auditSpanWithMetrics(t, "llamaindex", "openinference-openpipeline", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "llamaindex/openinference-openpipeline"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"llamaindex/openinference-openpipeline", genAIClientMetrics)
}
