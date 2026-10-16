package e2e

import (
	"fmt"
	"testing"
	"time"
)

func TestGoogleADKOpenInference(t *testing.T) {
	startApp(t, "google-adk/openinference")
	conversationID := triggerResearchConversation(t)

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

	// Both turns share one conversation id but land in separate traces.
	assertSpanExistsWithin(t, scopedDQL(fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == "google-adk/openinference"
| filter gen_ai.conversation.id == "%s"
| summarize traces = countDistinct(trace.id)
| filter traces >= 2
| limit 1`, conversationID)), 5*time.Minute)
}
