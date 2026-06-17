package e2e

import (
	"testing"
)

func TestAWSBedrockOneAgent(t *testing.T) {
	startApp(t, "aws-bedrock/oneagent")
	triggerHaiku(t, true)

	assertSpanExists(t,
		`fetch spans, from: now()-10m
| filter gen_ai.provider.name == "aws_bedrock" and dt.openpipeline.source == "oneagent"
| limit 1`,
	)
}
