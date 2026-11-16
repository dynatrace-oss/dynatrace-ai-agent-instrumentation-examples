package e2e

import (
	"fmt"
	"testing"
	"time"
)

func TestOpenAIAgentsOpenInference(t *testing.T) {
	startApp(t, "openai-agents/openinference")
	conversationID := triggerCSAgent(t)

	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "openai-agents/openinference"
| filter isNotNull(gen_ai.tool.name)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`),
		[]string{"gen_ai.tool.name", "gen_ai.conversation.id"}, nil)

	auditSpanWithMetrics(t, "openai-agents", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai-agents/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"openai-agents/openinference", genAIClientMetrics)

	// Both turns share one conversation id but land in separate traces.
	assertSpanExistsWithin(t, scopedDQL(fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == "openai-agents/openinference"
| filter gen_ai.conversation.id == "%s"
| summarize traces = countDistinct(trace.id)
| filter traces >= 2
| limit 1`, conversationID)), 5*time.Minute)
}
