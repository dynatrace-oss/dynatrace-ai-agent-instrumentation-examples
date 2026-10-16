package e2e

import (
	"testing"
	"time"
)

func TestLlamaIndexOpenInference(t *testing.T) {
	// CLI app: make run starts the Bindplane collector (Docker) then runs app.py once.
	// app.py sends two turns of one conversation, each in its own trace.
	startCLIApp(t, "llamaindex/openinference")

	auditSpanWithMetrics(t, "llamaindex", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "llamaindex/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"llamaindex/openinference", genAIClientMetrics)

	// Both turns share one conversation id but land in separate traces.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "llamaindex/openinference"
| filter isNotNull(gen_ai.conversation.id)
| summarize traces = countDistinct(trace.id), by: {gen_ai.conversation.id}
| filter traces >= 2
| limit 1`), 5*time.Minute)
}
