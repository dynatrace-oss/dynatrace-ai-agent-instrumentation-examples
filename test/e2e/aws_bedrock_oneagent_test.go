package e2e

import (
	"testing"
)

func TestAWSBedrockOneAgent(t *testing.T) {
	startApp(t, "aws-bedrock/oneagent")
	triggerHaiku(t, true)

	auditSpan(t, "aws-bedrock", "oneagent", BedrockProfile,
		`fetch spans, from: now()-10m
| filter gen_ai.provider.name == "aws_bedrock" and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| limit 1`)
}
