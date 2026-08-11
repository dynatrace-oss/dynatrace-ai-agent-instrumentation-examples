package e2e

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestRUMOpenTelemetry(t *testing.T) {
	startApp(t, "rum/opentelemetry")

	// Drive a real browser via Playwright so the Dynatrace RUM JS fires, injects
	// W3C traceparent headers, and generates session data visible in Experience Vitals.
	// The script asks 6 questions across providers; CI env triggers headless mode.
	cmd := exec.Command("make", "demo")
	cmd.Dir = filepath.Join(repoRoot(), "rum/opentelemetry")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		t.Fatalf("make trigger: %v", err)
	}

	// pydantic-ai emits gen_ai.client.token.usage natively but no duration metric.
	// gen_ai.client.operation.duration is derived from the LLM (chat) span and
	// gen_ai.invoke_agent.duration from pydantic-ai's agent-run span, which carries
	// gen_ai.operation.name == "invoke_agent" natively. On the default `make run`
	// path (direct OTLP export, what this test drives) both come from
	// openpipeline-rum.yaml deployed in the tenant; `make run-collector` derives the
	// same two via span_metrics connectors under a distinct service name.
	//
	// gen_ai.execute_tool.duration is deliberately NOT asserted: the agent registers
	// no tools, so there is no execute_tool span to derive it from. Likewise
	// gen_ai.invoke_workflow.duration — single agent, no workflow primitive. The
	// per-invocation call counts (inference_calls / tool_calls) cannot be derived
	// from spans at all.
	metrics := append(append([]string{}, genAIClientMetrics...), "gen_ai.invoke_agent.duration")

	auditSpanWithMetrics(t, "rum", "opentelemetry", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"rum/opentelemetry", metrics)

	t.Run("bedrock", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-bedrock", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter gen_ai.provider.name == "bedrock"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
	t.Run("azure", func(t *testing.T) {
		auditSpanOptional(t, "rum", "opentelemetry-azure", GenericProfile,
			`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry"
| filter gen_ai.provider.name == "azure"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
	})
}
