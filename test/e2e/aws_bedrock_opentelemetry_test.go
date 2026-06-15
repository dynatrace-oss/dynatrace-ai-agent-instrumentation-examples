package e2e

import (
	"testing"
)

func TestAWSBedrockOpenTelemetry(t *testing.T) {
	startCLIApp(t, "aws-bedrock/opentelemetry")

	assertGenAISpan(t,
		`fetch spans, from: now()-10m
| filter isNotNull(gen_ai.system)
| filter gen_ai.system == "aws.bedrock"
| limit 1`,
		"aws.bedrock",
	)
}
