package e2e

import (
	"testing"
)

func TestRUMOpenTelemetryCollector(t *testing.T) {
	// make run-collector routes the backend through a local OTel Collector, which
	// derives gen_ai.client.operation.duration from the pydantic-ai model-call span
	// (the only span carrying gen_ai.response.model) and gen_ai.invoke_agent.duration
	// from its agent-run span (gen_ai.operation.name == "invoke_agent", set natively)
	// via two span_metrics connectors.
	//
	// This is the path that asserts the durations, rather than the direct-export test:
	// on the direct path they come from openpipeline-rum.yaml, a tenant-side config
	// that a checkout cannot bring into existence. Deriving them in the collector
	// keeps the assertion true from a clean checkout on any tenant.
	//
	// The collector run reports under rum/opentelemetry-collector (set by the Makefile
	// recipe), distinct from the direct run's rum/opentelemetry. pollMetricExists
	// isolates by service name and time window only, so without the rename a derived
	// metric here could be satisfied by the other run, or the two paths' durations
	// would land on one series and double-count.
	startAppWithTarget(t, "rum/opentelemetry", "run-collector")
	driveRUMBrowserSession(t)

	// gen_ai.execute_tool.duration is deliberately absent: the agent is constructed
	// with a model and a system prompt and registers no tools, so pydantic-ai never
	// starts an execute_tool span. gen_ai.invoke_workflow.duration likewise — one
	// agent, no workflow primitive. The per-invocation call counts
	// (inference_calls / tool_calls) cannot be derived from spans at all; they have
	// to be recorded by the framework at invocation close.
	metrics := append(append([]string{}, genAIClientMetrics...), genAIInvokeAgentDurationMetric)

	auditSpanWithMetrics(t, "rum", "opentelemetry-collector", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "rum/opentelemetry-collector"
| filter isNotNull(gen_ai.conversation.id)
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"rum/opentelemetry-collector", metrics)
}
