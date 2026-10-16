package e2e

import (
	"testing"
)

func TestLlamaIndexOpenInference(t *testing.T) {
	// CLI app: make run starts the Bindplane collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by the LlamaIndex pipeline in app.py.
	startCLIApp(t, "llamaindex/openinference")

	auditSpanWithMetrics(t, "llamaindex", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "llamaindex/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"llamaindex/openinference", genAIClientMetrics)
}
