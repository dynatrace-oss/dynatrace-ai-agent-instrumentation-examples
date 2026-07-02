package e2e

import (
	"testing"
)

func TestAWSBedrockOneAgent(t *testing.T) {
	startApp(t, "aws-bedrock/oneagent")
	triggerHaiku(t, true)

	auditSpan(t, "aws-bedrock", "oneagent", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/oneagent"
| filter (gen_ai.provider.name == "aws_bedrock" or gen_ai.system == "aws_bedrock") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
