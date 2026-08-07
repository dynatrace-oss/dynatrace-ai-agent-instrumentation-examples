package e2e

import (
	"testing"
)

func TestMicrosoftAgentFrameworkOpenTelemetryCollector(t *testing.T) {
	// CLI app: make run-collector routes the app through a local OTel Collector,
	// which derives gen_ai.invoke_agent.duration, gen_ai.execute_tool.duration and
	// gen_ai.invoke_workflow.duration from the agent, tool and workflow spans via
	// three spanmetrics connectors. service.name == "microsoft-agent-framework-collector"
	// keeps this data set distinct from the direct-export test
	// (service.name == "microsoft-agent-framework"), so a derived metric can never
	// be satisfied by the other run.
	startCLIAppWithTarget(t, "microsoft-agent-framework/opentelemetry", "run-collector")

	// This path carries the full set: the natively emitted gen_ai.client.* metrics
	// plus every GenAI agent/tool/workflow metric — the in-process call counts and
	// the three collector-derived durations.
	metrics := append(append([]string{}, genAIClientMetrics...), genAIAgentMetrics...)

	auditSpanWithMetrics(t, "microsoft-agent-framework", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "microsoft-agent-framework-collector"
| filter gen_ai.provider.name == "microsoft.agent_framework" or gen_ai.system == "microsoft.agent_framework"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"microsoft-agent-framework-collector", metrics)
}
