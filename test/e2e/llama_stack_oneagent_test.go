package e2e

import (
	"testing"
)

func TestLlamaStackOneAgent(t *testing.T) {
	startApp(t, "llama-stack/oneagent")
	triggerHaiku(t, false)

	// Llama Stack calls Ollama through the openai client, so the span comes
	// from OneAgent's OpenAI sensor; the provider value is not pinned here.
	auditSpan(t, "llama-stack", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "llama-stack/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
