package e2e

import (
	"testing"
)

func TestPydanticAIOpenTelemetry(t *testing.T) {
	startAppWithTarget(t, "pydantic-ai/opentelemetry", "run")
	// Fire 6 requests so the random provider selection covers both Azure and Bedrock.
	// With 3 requests, the odds of missing Bedrock entirely by chance are ~3.7%
	// (1/3 per request); 6 requests brings that down to ~0.1%.
	for range 6 {
		triggerMusicAgent(t)
	}
	triggerMusicAgentGuardrail(t)

	t.Run("bedrock", func(t *testing.T) {
		// Targets the pydantic-ai chat span (provider "bedrock", carries usage tokens).
		// Spans from the ask-guardrail flow are excluded via a trace-id lookup so this audits
		// the /api/ask flow only; the guardrail flow has its own subtest below.
		auditSpanOptionalWithMetrics(t, "pydantic-ai", "opentelemetry-bedrock", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter gen_ai.provider.name == "bedrock" or gen_ai.system == "bedrock"
| filter isNotNull(gen_ai.response.model)
| filter isNull(span.status_code) or span.status_code != "error"
| lookup [fetch spans, from: now()-10m
    | filter service.name == "pydantic-ai-music-agent"
    | filter isNotNull(gen_ai.guardrail.id)
    | fields trace.id],
  sourceField: trace.id, lookupField: trace.id
| filter isNull(lookup.trace.id)
| limit 1`,
			"pydantic-ai-music-agent", genAIClientMetrics)
	})
	t.Run("azure", func(t *testing.T) {
		auditSpanOptionalWithMetrics(t, "pydantic-ai", "opentelemetry-azure", AzureProfile,
			`fetch spans, from: now()-10m
| filter service.name == "pydantic-ai-music-agent"
| filter gen_ai.provider.name == "azure" or gen_ai.system == "azure"
| filter isNotNull(gen_ai.response.model)
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
