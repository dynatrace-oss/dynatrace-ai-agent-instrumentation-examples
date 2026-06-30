package e2e

import "testing"

func TestAWSStrandsOpenTelemetryOpenPipeline(t *testing.T) {
	// CLI app: make run-openpipeline sends spans directly to Dynatrace (no collector).
	// Attribute transformation happens server-side via the OpenPipeline strands-agents-ai-spans pipeline.
	// service.name == "aws-strands/opentelemetry-openpipeline" keeps this data set distinct
	// from the collector-based test (service.name == "aws-strands/opentelemetry").
	startCLIAppWithTarget(t, "aws-strands/opentelemetry", "run-openpipeline")

	// gen_ai.bedrock.guardrail.* (AR-017/AR-018/AR-019) are not emitted
	// because the demo does not configure Bedrock guardrails — expected FAIL in report.
	auditSpan(t, "aws-strands", "opentelemetry-openpipeline", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-strands/opentelemetry-openpipeline"
| filter isNotNull(gen_ai.system)
| filter isNotNull(gen_ai.request.model)
| limit 1`)
}
