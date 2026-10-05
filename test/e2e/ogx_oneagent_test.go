package e2e

import (
	"testing"
)

func TestOGXOneAgent(t *testing.T) {
	startApp(t, "ogx/oneagent")
	triggerHaiku(t, false)

	// OGX calls Ollama through the openai client, so the span comes
	// from OneAgent's OpenAI sensor; the provider value is not pinned here.
	auditSpan(t, "ogx", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "ogx/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
