package e2e

import (
	"testing"
)

func TestAWSStrandsOpenTelemetry(t *testing.T) {
	startCLIApp(t, "aws-strands/opentelemetry")

	// gen_ai.bedrock.guardrail.* (AR-017/AR-018/AR-019) are not emitted
	// because the demo does not configure Bedrock guardrails — expected FAIL in report.
	// The otel-collector derives gen_ai.client.token.usage and
	// gen_ai.client.operation.duration from span attributes/durations via the
	// signaltometrics and span_metrics connectors; results are recorded alongside
	// the span audit in the generated report.
	//
	// The same collector derives gen_ai.invoke_agent.duration and
	// gen_ai.execute_tool.duration from the Strands agent and tool spans, which
	// carry gen_ai.operation.name natively. gen_ai.invoke_workflow.duration is not
	// asserted: Strands has no workflow primitive, so this demo has no span to
	// derive it from and deliberately does not emit it. The per-invocation call
	// counts (gen_ai.invoke_agent.inference_calls / .tool_calls) are likewise not
	// asserted — they cannot be derived from spans at all.
	metrics := append(append([]string{}, genAIClientMetrics...), genAIAgentDurationMetrics...)

	auditSpanWithMetrics(t, "aws-strands", "opentelemetry", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-strands/opentelemetry"
| filter isNotNull(gen_ai.provider.name)
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`,
		"aws-strands/opentelemetry", metrics)
}
