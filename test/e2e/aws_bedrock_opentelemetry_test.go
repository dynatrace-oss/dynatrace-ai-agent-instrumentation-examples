package e2e

import (
	"testing"
)

func TestAWSBedrockOpenTelemetry(t *testing.T) {
	startCLIApp(t, "aws-bedrock/opentelemetry")

	// gen_ai.response.model (AR-005) is not emitted by BedrockInstrumentor/BotocoreInstrumentor;
	// tracked as a gap in test/e2e/sdk-analysis/aws-bedrock-opentelemetry.md.
	auditSpan(t, "aws-bedrock", "opentelemetry", BedrockProfile,
		`fetch spans, from: now()-10m
| filter gen_ai.provider.name == "aws.bedrock" or gen_ai.system == "aws.bedrock"
| filter service.name == "aws-bedrock/opentelemetry"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
