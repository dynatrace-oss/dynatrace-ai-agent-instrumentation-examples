package e2e

import (
	"testing"
)

func TestAWSBedrockOpenInference(t *testing.T) {
	startApp(t, "aws-bedrock/openinference")
	triggerHaiku(t, true)

	assertGenAISpan(t,
		`fetch spans, from: now()-10m
| filter gen_ai.system == "aws.bedrock"
| filter service.name == "haiku-writer"
| limit 1`,
		"aws.bedrock",
	)
}
