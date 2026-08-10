package e2e

import (
	"testing"
)

func TestMCPOpenTelemetryCollector(t *testing.T) {
	// make run-collector points both processes (the LangGraph agent and the
	// TypeScript MCP server) at a local OTel Collector, which derives
	// gen_ai.invoke_agent.duration and gen_ai.execute_tool.duration from the spans
	// via two span_metrics connectors.
	//
	// The collector renames only the agent's service to "mcp-agent-demo-collector"
	// — the MCP server keeps "weather-mcp-server", since the cross-service trace
	// is the point of the demo. The rename keeps this data set distinct from the
	// direct-export test (service.name == "mcp-agent-demo"), so a derived metric
	// can never be satisfied by the other run.
	startAppWithTarget(t, "mcp/opentelemetry", "run-collector")
	triggerMCPAgent(t)

	// No collector-side rewriting is involved: opentelemetry-instrumentation-langchain
	// labels the graph run "invoke_agent" and every LangChain tool span
	// "execute_tool" itself. Both the local @tool("get_city") and the weather tool
	// reached over MCP are LangChain tools by the time the agent calls them, so the
	// ReAct loop produces at least one execute_tool span per request.
	metrics := []string{
		"gen_ai.invoke_agent.duration",
		"gen_ai.execute_tool.duration",
	}

	auditSpanWithMetrics(t, "mcp", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "mcp-agent-demo-collector"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"mcp-agent-demo-collector", metrics)
}
