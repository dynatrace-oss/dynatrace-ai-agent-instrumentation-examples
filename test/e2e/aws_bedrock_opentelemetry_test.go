package e2e

import (
	"testing"
)

func TestAWSBedrockOpenTelemetry(t *testing.T) {
	startCLIApp(t, "aws-bedrock/opentelemetry")

	assertGenAISpan(t,
		`fetch spans, from: now()-10m
| filter gen_ai.system == "aws.bedrock"
| filter service.name == "bedrock_example_app"
| limit 1`,
		"aws.bedrock",
	)
}
