package e2e

import (
	"testing"
)

func TestLiteLLMOneAgent(t *testing.T) {
	startOpenAICompatibleMock(t, "GROQ_API_KEY", "GROQ_API_BASE")
	startApp(t, "litellm/oneagent")
	triggerHaiku(t, true)

	// The OneAgent LiteLLM sensor always reports gen_ai.provider.name "litellm".
	auditSpan(t, "litellm", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "litellm/oneagent"
| filter gen_ai.provider.name == "litellm"
| filter gen_ai.operation.name == "chat"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"Backend mocked: an in-process OpenAI-compatible stub serves Groq requests via GROQ_API_BASE. Set a real GROQ_API_KEY secret for live validation.")
}
