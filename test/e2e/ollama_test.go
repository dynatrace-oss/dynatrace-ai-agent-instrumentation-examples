package e2e

import (
	"testing"
	"time"
)

func TestOllamaOneAgent(t *testing.T) {
	startApp(t, "ollama/oneagent")
	triggerHaiku(t, false)

	// Requires the opt-in OneAgent prompt capture feature for this sensor.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "ollama/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.input.messages) and isNotNull(gen_ai.output.messages)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	auditSpan(t, "ollama", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "ollama/oneagent"
| filter (gen_ai.provider.name == "ollama" or gen_ai.system == "ollama") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
