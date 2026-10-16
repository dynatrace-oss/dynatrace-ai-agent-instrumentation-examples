package e2e

import (
	"testing"
)

func TestCrewAIOpenInference(t *testing.T) {
	startApp(t, "crewai/openinference")
	makeRequest(t, "crewai/openinference", "request")

	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "crewai/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`),
		[]string{"gen_ai.provider.name", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "gen_ai.conversation.id"}, nil)

	auditSpanWithMetrics(t, "crewai", "openinference", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "crewai/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"crewai/openinference", genAIClientMetrics)
}
