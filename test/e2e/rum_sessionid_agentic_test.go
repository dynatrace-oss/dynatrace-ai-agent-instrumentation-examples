package e2e

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestRUMOpenTelemetry(t *testing.T) {
	// One test for this demo, on the collector path only.
	//
	// `make run-collector` routes the backend through a local OTel Collector, which
	// derives gen_ai.client.operation.duration from the pydantic-ai model-call span
	// (the only span carrying gen_ai.response.model) and gen_ai.invoke_agent.duration
	// from its agent-run span (gen_ai.operation.name == "invoke_agent", set natively)
	// via two span_metrics connectors. Everything still reaches Dynatrace, so this run
	// exercises the same app, the same browser flow, the same spans and the same
	// profile as a direct-export run, plus the two derived metrics.
	//
	// A direct-export run is deliberately NOT tested. On that path the durations come
	// from openpipeline-rum.yaml, a tenant-side config that a checkout cannot bring
	// into existence, so the assertion would fail wherever the pipeline has not been
	// deployed while telling us nothing the collector run does not already cover.
	// (If the pipeline is ever deployed to the e2e tenant, add a second
	// `-openpipeline` suite for it, as aws-strands does, rather than reinstating a
	// direct run here.)
	//
	// The collector run reports under rum/opentelemetry-collector, set by the Makefile
	// recipe. The RUM-to-backend correlation is unaffected: the browser links to the
	// backend through the W3C traceparent header, not through service.name.
	startAppWithTarget(t, "rum/opentelemetry", "run-collector")

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
