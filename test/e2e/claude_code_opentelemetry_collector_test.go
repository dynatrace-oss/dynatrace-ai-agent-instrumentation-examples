package e2e

import "testing"

func TestClaudeCodeOpenTelemetryCollector(t *testing.T) {
	startAnthropicCompatibleMock(t)

	// The target starts the repository's collector enrichment example, executes
	// one headless Claude Code turn, flushes native telemetry, and exits. The local
	// Anthropic-compatible mock is used when no real CI credential is configured.
	startCLIAppWithTarget(t, "ai-coding-agents/claude-code", "run-collector")

	anchor := `fetch spans, from: now()-10m
| filter service.name == "claude-code"
| filter span.name == "claude_code.llm_request"
| filter gen_ai.operation.name == "chat"
| filter gen_ai.provider.name == "anthropic"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(gen_ai.response.model)
| filter isNotNull(gen_ai.usage.input_tokens)
| filter isNotNull(gen_ai.usage.output_tokens)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`

	auditSpan(t, "claude-code", "opentelemetry-collector", GenericProfile, anchor,
		"Backend mocked when Anthropic credentials are absent: an in-process httptest server serves the Messages API via ANTHROPIC_BASE_URL.")
	assertSpanWithAttrs(t, scopedDQL(anchor), []string{
		"gen_ai.provider.name",
		"gen_ai.operation.name",
		"gen_ai.request.model",
		"gen_ai.response.model",
		"gen_ai.usage.input_tokens",
		"gen_ai.usage.output_tokens",
	}, nil)

	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "claude-code"
| filter span.name == "claude_code.interaction"
| filter gen_ai.operation.name == "invoke_agent"
| filter gen_ai.provider.name == "anthropic"
| sort timestamp desc
| limit 1`), []string{
		"gen_ai.agent.name",
		"gen_ai.agent.id",
	}, nil)
}
