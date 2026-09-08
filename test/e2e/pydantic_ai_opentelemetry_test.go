package e2e

import (
	"testing"
)

func TestPydanticAIOpenTelemetry(t *testing.T) {
	startAppWithTarget(t, "pydantic-ai/opentelemetry", "run-collector")
	// Fire 3 requests so the random provider selection covers both Azure and Bedrock.
	for range 3 {
		triggerMusicAgent(t)
	}
	triggerMusicAgentGuardrail(t)

	t.Run("bedrock", func(t *testing.T) {
		auditSpanOptionalWithMetrics(t, "pydantic-ai", "opentelemetry-bedrock", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter gen_ai.provider.name == "AWS Bedrock" or gen_ai.system == "AWS Bedrock"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
			"pydantic-ai-music-agent", genAIClientMetrics)
	})
	t.Run("azure", func(t *testing.T) {
		auditSpanOptionalWithMetrics(t, "pydantic-ai", "opentelemetry-azure", AzureProfile,
			`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter gen_ai.provider.name == "Azure OpenAI" or gen_ai.system == "Azure OpenAI"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
			"pydantic-ai-music-agent", genAIClientMetrics)
	})
	t.Run("bedrock-guardrail", func(t *testing.T) {
		auditGuardrailSpan(t, "pydantic-ai", "opentelemetry",
			`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter isNotNull(gen_ai.guardrail.id)
| sort timestamp desc
| limit 1`)
	})
}
