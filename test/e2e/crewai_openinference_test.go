package e2e

import (
	"fmt"
	"testing"
	"time"
)

func TestCrewAIOpenInference(t *testing.T) {
	startApp(t, "crewai/openinference")
	// The request target sends two turns with this conversation id.
	conversationID := fmt.Sprintf("crewai-oi-%d", time.Now().UnixNano())
	t.Setenv("CONVERSATION_ID", conversationID)
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

	// Both turns share one conversation id but land in separate traces.
	assertSpanExistsWithin(t, scopedDQL(fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == "crewai/openinference"
| filter gen_ai.conversation.id == "%s"
| summarize traces = countDistinct(trace.id)
| filter traces >= 2
| limit 1`, conversationID)), 5*time.Minute)
}
