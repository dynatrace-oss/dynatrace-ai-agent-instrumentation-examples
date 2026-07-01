package e2e

import (
	"testing"
)

func TestOllamaOneAgent(t *testing.T) {
	startApp(t, "ollama/oneagent")
	triggerHaiku(t, false)

	auditSpan(t, "ollama", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "ollama/oneagent"
| filter gen_ai.provider.name == "ollama" and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
