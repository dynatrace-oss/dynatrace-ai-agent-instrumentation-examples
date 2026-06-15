package e2e

import (
	"testing"
)

func TestAWSBedrockOpenInference(t *testing.T) {
	startApp(t, "aws-bedrock/openinference")
	triggerHaiku(t, true)

	assertGenAISpan(t,
		`fetch spans, from: now()-10m
| filter isNotNull(gen_ai.system)
| filter gen_ai.system == "aws.bedrock"
| limit 1`,
		"aws.bedrock",
	)
}
