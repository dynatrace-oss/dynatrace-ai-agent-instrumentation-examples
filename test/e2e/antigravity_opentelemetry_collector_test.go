package e2e

import (
	"testing"
)

func TestAntigravityOpenTelemetryCollector(t *testing.T) {
	// CLI app: make run-collector starts the OTel Collector (Docker), then runs
	// app.py once. There is no HTTP server and no trigger; the agent turn is
	// issued by app.py itself.
	//
	// The collector path is the only suite for this demo. The Antigravity SDK
	// emits no metrics at all, so every metric asserted below is derived from
	// its spans: token usage and client duration from the invoke_agent span
	// (which app.py enriches with the model and token counts, since neither is
	// reachable from a collector rule), and the agent/tool durations from span
	// timings. collector.yaml renames service.name to "antigravity-collector"
	// because app.py pins it on the Resource.
	startCLIAppWithTarget(t, "ai-coding-agents/antigravity", "run-collector")

	metrics := append(append([]string{}, genAIClientMetrics...), genAIAgentDurationMetrics...)

	auditSpanWithMetrics(t, "antigravity", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "antigravity-collector"
| filter gen_ai.operation.name == "invoke_agent"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"antigravity-collector", metrics,
		"gen_ai.response.model is mirrored from the request model by the collector: the SDK "+
			"reports no resolved model anywhere. Token counts are turn-level (all model "+
			"invocations in one agent turn), which is the narrowest granularity the SDK exposes.")

	// The audit above anchors on the agent span and reports attribute gaps
	// without failing, so the two things most likely to regress silently get
	// their own hard assertions.
	//
	// Prompt and response content is opt-in and app.py turns it on; if that
	// regresses, the audit would still pass because AR-011/AR-012 are optional.
	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "antigravity-collector"
| filter gen_ai.operation.name == "invoke_agent"
| sort timestamp desc
| limit 1`),
		[]string{
			"gen_ai.input.messages",
			"gen_ai.output.messages",
			"gen_ai.system_instructions",
			"gen_ai.request.model",
			"gen_ai.usage.input_tokens",
			"gen_ai.usage.output_tokens",
		}, nil)

	// The tool span only appears if the model actually calls the registered
	// function tool.
	assertSpanExists(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "antigravity-collector"
| filter gen_ai.operation.name == "execute_tool"
| filter gen_ai.tool.name == "list_observability_signals"
| limit 1`))
}
