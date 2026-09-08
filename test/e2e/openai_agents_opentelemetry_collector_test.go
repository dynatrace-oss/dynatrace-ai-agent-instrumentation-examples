package e2e

import (
	"testing"
)

func TestOpenAIAgentsOpenTelemetryCollector(t *testing.T) {
	// make run-collector routes the app through a local OTel Collector, which
	// derives the three GenAI agent duration metrics from the spans via
	// span_metrics connectors. Traceloop.init pins service.name on the Resource,
	// so the collector renames it to "openai-cs-agents-collector" with a resource
	// processor; that keeps this data set distinct from the direct-export test
	// (service.name == "openai-cs-agents"), so a derived metric can never be
	// satisfied by the other run.
	startAppWithTarget(t, "openai-agents/opentelemetry", "run-collector")
	triggerCSAgent(t)

	// All three durations are asserted. The instrumentation sets the spec enum
	// itself on the agent and function-tool spans; only the per-trace root span
	// ("Agent Workflow", traceloop.span.kind = workflow, no enum) needs the
	// collector's transform to become invoke_workflow.
	//
	// execute_tool depends on the model actually calling a tool. triggerCSAgent
	// asks about baggage allowance and then a seat change, both of which route to
	// function tools (faq_lookup_tool / baggage_tool, update_seat), so a run
	// without a tool call would be the anomaly rather than the norm.
	metrics := []string{
		"gen_ai.invoke_agent.duration",
		"gen_ai.execute_tool.duration",
		"gen_ai.invoke_workflow.duration",
	}

	auditSpanWithMetrics(t, "openai-agents", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai-cs-agents-collector"
| filter gen_ai.provider.name == "azure.ai.openai" or gen_ai.system == "azure.ai.openai"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"openai-cs-agents-collector", metrics)
}
