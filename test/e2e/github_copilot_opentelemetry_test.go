package e2e

import (
	"os"
	"testing"
)

// TestGitHubCopilotOpenTelemetry exercises the Copilot runtime's native OTel
// export. The runtime emits gen_ai.* spans and metrics itself, so there is no
// instrumentation library and no manual spans to assert against.
//
// The run needs no GitHub token and no Copilot entitlement: SessionConfig.provider
// puts the session in BYOK mode, which bypasses Copilot API authentication and
// sends inference to the shared OpenAI-compatible mock instead.
//
// Metrics must go through the collector in ../../ai-coding-agents/github-copilot-sdk/collector.yaml:
// the runtime exports cumulative temporality with no option to change it, and
// Dynatrace rejects cumulative metrics with HTTP 400.
func TestGitHubCopilotOpenTelemetry(t *testing.T) {
	startOpenAICompatibleMock(t, "COPILOT_PROVIDER_API_KEY", "COPILOT_PROVIDER_BASE_URL")

	// The SDK appends /chat/completions to the configured baseUrl, so it needs
	// the /v1 prefix the mock serves on.
	if base := os.Getenv("COPILOT_PROVIDER_BASE_URL"); base != "" {
		t.Setenv("COPILOT_PROVIDER_BASE_URL", base+"/v1")
	}

	// Content capture is off by default in the example for privacy, but the
	// prompts and responses here come from the mock, so enabling it is safe and
	// exercises gen_ai.input.messages, gen_ai.output.messages and
	// gen_ai.system_instructions.
	t.Setenv("COPILOT_CAPTURE_CONTENT", "true")

	// CLI app: make run builds TypeScript, starts the collector (Docker), then
	// runs dist/index.js once. No triggerHaiku; make run issues the request.
	startCLIApp(t, "ai-coding-agents/github-copilot-sdk")

	auditSpanWithMetrics(t, "github-copilot", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "github-copilot"
| filter gen_ai.operation.name == "chat"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"github-copilot", genAIClientMetrics)
}
