package e2e

import (
	"testing"
)

func TestAWSBedrockOpenTelemetry(t *testing.T) {
	startCLIApp(t, "aws-bedrock/opentelemetry")

	// gen_ai.response.model (AR-005) is not emitted by BedrockInstrumentor/BotocoreInstrumentor;
	// tracked as a gap in test/e2e/sdk-analysis/aws-bedrock-opentelemetry.md.
	// Traceloop emits the OTel GenAI client metrics; delta temporality (added in
	// main.py) is required for Dynatrace to accept them. The metric results are
	// recorded in the generated report alongside the span audit.
	auditSpanWithMetrics(t, "aws-bedrock", "opentelemetry", BedrockProfile,
		`fetch spans, from: now()-10m
| filter gen_ai.provider.name == "aws.bedrock" or gen_ai.system == "aws.bedrock"
| filter service.name == "aws-bedrock/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"aws-bedrock/opentelemetry", awsBedrockOpenTelemetryMetrics())
}

// awsBedrockOpenTelemetryMetrics is the client metrics plus the two agent
// durations this demo derives in its collector config.
//
// The demo is built from Traceloop decorators, so its agent and workflow spans
// carry traceloop.span.kind and no gen_ai.operation.name; the collector's
// transform/traceloop_operation_name maps the kind onto the spec enum and the
// span_metrics connectors derive the durations from there.
//
// gen_ai.execute_tool.duration is absent because the demo has no @tool — its
// only sub-boundaries are @task, which is not a spec operation. That is also
// why genAIAgentDurationMetrics is not reused here: it assumes a tool span.
func awsBedrockOpenTelemetryMetrics() []string {
	metrics := append([]string{}, genAIClientMetrics...)
	return append(metrics,
		"gen_ai.invoke_agent.duration",
		"gen_ai.invoke_workflow.duration",
	)
}
