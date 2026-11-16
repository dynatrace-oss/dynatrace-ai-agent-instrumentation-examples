package e2e

import (
	"fmt"
	"testing"
	"time"
)

func TestTogetherOpenInference(t *testing.T) {
	startOpenAICompatibleMock(t, "TOGETHER_API_KEY", "TOGETHER_BASE_URL")
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku - the haiku request is issued by make run itself.
	// app.py runs two turns under CONVERSATION_ID, each in its own trace.
	conversationID := fmt.Sprintf("e2e-together-%d", time.Now().UnixNano())
	t.Setenv("CONVERSATION_ID", conversationID)
	startCLIApp(t, "together/openinference")

	auditSpanWithMetrics(t, "together", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "together/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"together/openinference", genAIClientMetrics,
		"Backend mocked: a local HTTP stub serves Together AI-compatible chat completions via TOGETHER_BASE_URL. Replace with a real TOGETHER_API_KEY secret for live validation.")

	assertSpanExistsWithin(t, scopedDQL(fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == "together/openinference"
| filter gen_ai.conversation.id == "%s"
| summarize traces = countDistinct(trace.id)
| filter traces >= 2
| limit 1`, conversationID)), 5*time.Minute)
}
