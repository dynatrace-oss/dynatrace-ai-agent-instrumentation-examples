package e2e

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestRUMOpenTelemetry(t *testing.T) {
	// `make run` routes the backend through a local OTel Collector, which derives
	// gen_ai.client.operation.duration from the pydantic-ai model-call span (the only
	// span carrying gen_ai.response.model) and gen_ai.invoke_agent.duration from its
	// agent-run span (gen_ai.operation.name == "invoke_agent") via two span_metrics
	// connectors.
	//
	// The run reports under rum/opentelemetry-collector, set by the Makefile recipe.
	// The RUM-to-backend correlation is unaffected: the browser links to the backend
	// through the W3C traceparent header, not through service.name.
	startAppWithTarget(t, "rum/opentelemetry", "run")

	driveRUMBrowserSession(t)

	// gen_ai.execute_tool.duration is deliberately absent: the agent is constructed
	// with a model and a system prompt and registers no tools, so pydantic-ai never
	// starts an execute_tool span. gen_ai.invoke_workflow.duration likewise, since
	// this is one agent with no workflow primitive. The per-invocation call counts
	// (inference_calls / tool_calls) cannot be derived from spans at all; they have to
	// be recorded by the framework at invocation close.
	metrics := append(append([]string{}, genAIClientMetrics...), genAIInvokeAgentDurationMetric)

	auditSpanWithMetrics(t, "rum", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry-collector"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"rum/opentelemetry-collector", metrics)

	t.Run("bedrock", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-bedrock", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry-collector"
| filter gen_ai.provider.name == "bedrock"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
	t.Run("azure", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-azure", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry-collector"
| filter gen_ai.provider.name == "azure"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
}

// driveRUMBrowserSession drives a real browser via Playwright so the Dynatrace RUM
// JS fires, injects W3C traceparent headers, and generates session data visible in
// Experience Vitals. The script asks 6 questions across providers; the CI env
// triggers headless mode.
func driveRUMBrowserSession(t *testing.T) {
	t.Helper()
	cmd := exec.Command("make", "demo")
	cmd.Dir = filepath.Join(repoRoot(), "rum/opentelemetry")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		t.Fatalf("make demo: %v", err)
	}
}
