package e2e

import (
	"testing"
)

func TestPydanticAIOpenTelemetry(t *testing.T) {
	startApp(t, "pydantic-ai/opentelemetry")
	// Fire 3 requests so the random provider selection covers both Azure and Bedrock.
	for range 3 {
		triggerMusicAgent(t)
	}

	t.Run("bedrock", func(t *testing.T) {
		auditSpanOptional(t, "pydantic-ai", "opentelemetry-bedrock", BedrockProfile,
			`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter gen_ai.provider.name == "AWS Bedrock"
| filter isNotNull(gen_ai.request.model)
| limit 1`)
	})
	t.Run("azure", func(t *testing.T) {
		auditSpanOptional(t, "pydantic-ai", "opentelemetry-azure", AzureProfile,
			`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter gen_ai.provider.name == "Azure OpenAI"
| filter isNotNull(gen_ai.request.model)
| limit 1`)
	})
}
