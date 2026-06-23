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

	auditSpan(t, "pydantic-ai", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter isNotNull(gen_ai.provider.name)
| limit 1`)
}
