package e2e

import (
	"testing"
)

func TestGoogleADKOpenInference(t *testing.T) {
	startApp(t, "google-adk/openinference")
	triggerResearch(t)

	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "google-adk/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`),
		[]string{"gen_ai.request.model", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"}, nil)

	auditSpanWithMetrics(t, "google-adk", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"google-adk/openinference", genAIClientMetrics)
}
