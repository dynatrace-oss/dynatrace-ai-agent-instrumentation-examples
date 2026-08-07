package e2e

import (
	"testing"
)

func TestGoogleADKOpenTelemetryCollector(t *testing.T) {
	// make run-collector routes the app through a local OTel Collector, which
	// derives gen_ai.invoke_agent.duration and gen_ai.execute_tool.duration from
	// ADK's own invoke_agent / execute_tool spans via two span_metrics connectors.
	// app.py pins service.name on the Resource, so the collector renames it to
	// "google-adk-collector" with a resource processor; that keeps this data set
	// distinct from the direct-export test (service.name == "google-adk-samples"),
	// so a derived metric can never be satisfied by the other run.
	startAppWithTarget(t, "google-adk/opentelemetry", "run-collector")
	triggerResearch(t)

	// gen_ai.invoke_workflow.duration is absent by design: ADK only opens an
	// invoke_workflow span for a google.adk.workflow.Workflow node, and this demo
	// is an LlmAgent with AgentTool sub-agents.
	metrics := append(append([]string{}, genAIClientMetrics...), genAIAgentDurationMetrics...)

	auditSpanWithMetrics(t, "google-adk", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk-collector"
| filter gen_ai.system == "gemini"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"google-adk-collector", metrics)
}
