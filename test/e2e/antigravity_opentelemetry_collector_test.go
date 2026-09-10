package e2e

import (
	"testing"
)

func TestAntigravityOpenTelemetryCollector(t *testing.T) {
	// CLI app: make run-collector starts the OTel Collector (Docker), then runs
	// app.py once. There is no HTTP server and no trigger; the agent turn is
	// issued by app.py itself.
	//
	// The collector path is the only suite for this demo. It exercises the same
	// agent as the direct-export path and additionally derives
	// gen_ai.invoke_agent.duration and gen_ai.execute_tool.duration from the
	// SDK's own spans via two span_metrics connectors; the SDK emits no metrics
	// of its own. collector.yaml renames service.name to "antigravity-collector"
	// because app.py pins it on the Resource.
	startCLIAppWithTarget(t, "ai-coding-agents/antigravity", "run-collector")

	// genAIClientMetrics is deliberately absent: the Antigravity OTel hooks trace
	// agent turns, steps and tool calls, never the underlying Gemini request, so
	// there is no client span to derive token usage or operation duration from.
	metrics := append([]string{}, genAIAgentDurationMetrics...)

	auditSpanWithMetrics(t, "antigravity", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "antigravity-collector"
| filter gen_ai.operation.name == "invoke_agent"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"antigravity-collector", metrics,
		"Antigravity SDK OTel hooks emit agent/step/tool spans only. gen_ai.request.model, "+
			"gen_ai.response.model and token counts (AR-004 to AR-007) are never set on any span: "+
			"the hooks wrap the agent loop, not the Gemini client. gen_ai.provider.name comes from "+
			"the Resource in app.py.")

	// The tool span is the part most likely to regress silently: it only appears
	// if the model actually calls the registered function tool, and the audit
	// above anchors on the agent span.
	assertSpanExists(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "antigravity-collector"
| filter gen_ai.operation.name == "execute_tool"
| filter gen_ai.tool.name == "list_observability_signals"
| limit 1`))
}
