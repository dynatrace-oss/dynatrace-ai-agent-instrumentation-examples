package e2e

import (
	"testing"
)

func TestLiteLLMOpenTelemetry(t *testing.T) {
	// CI sets OPENAI_API_BASE to the Azure endpoint for other tests; clear it so
	// LiteLLM routes gpt-4o-mini to api.openai.com, not the Azure deployment.
	t.Setenv("OPENAI_API_BASE", "")

	startApp(t, "litellm/opentelemetry")
	triggerLiteLLMChat(t)

	auditSpan(t, "litellm", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "litellm-gateway"
| filter isNotNull(gen_ai.system)
| limit 1`)
}
