package e2e

import (
	"testing"
)

func TestGoogleADKOpenTelemetryCollector(t *testing.T) {
	// make run-collector routes the app through a local OTel Collector, which
	// derives gen_ai.invoke_agent.duration and gen_ai.execute_tool.duration from
	// ADK's own invoke_agent / execute_tool spans via two span_metrics connectors.
	// app.py pins service.name on the Resource, so the collector renames it to
	// "google-adk-collector" with a resource processor.
	//
	// This is the only suite for this demo. The direct-export test was dropped: the
	// collector run exercises the same app, request and profile plus the derived
	// metrics, and the direct run additionally failed AR-005 by design (ADK records
	// the response model only as a metric attribute, never as a span attribute), so
	// it asserted a gap no config in this demo can close.
	startAppWithTarget(t, "google-adk/opentelemetry", "run-collector")
	triggerResearch(t)

	// gen_ai.invoke_workflow.duration is absent by design: ADK only opens an
	// invoke_workflow span for a google.adk.workflow.Workflow node, and this demo
	// is an LlmAgent with AgentTool sub-agents.
	//
	// gen_ai.execute_tool.duration depends on the coordinator actually delegating to
	// an AgentTool. The request app.py sends asks for recent citing work, which it
	// cannot answer without the websearch tool; a request that only asks for a
	// summary lets the model answer from its weights and produces a trace with no
	// execute_tool span, which is what made this assertion flaky before.
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
