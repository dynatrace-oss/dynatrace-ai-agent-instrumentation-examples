package e2e

import (
	"testing"
)

func TestAWSBedrockOneAgent(t *testing.T) {
	startApp(t, "aws-bedrock/oneagent")
	triggerHaiku(t, true)

	assertGenAISpan(t,
		`fetch spans, from: now()-10m
| filter gen_ai.provider_name == "aws_bedrock" and dt.openpipeline.source == "oneagent"
| limit 1`,
		"aws.bedrock",
	)
}
