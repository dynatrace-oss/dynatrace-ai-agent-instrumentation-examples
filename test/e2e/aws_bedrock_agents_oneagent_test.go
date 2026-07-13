package e2e

import (
	"testing"
)

func TestAWSBedrockAgentsOneAgent(t *testing.T) {
	startApp(t, "aws-bedrock-agents/oneagent")
	triggerAgent(t)

	// gen_ai.bedrock.guardrail.* (AR-017/AR-018/AR-019) are not emitted
	// because the demo does not configure Bedrock guardrails — expected FAIL in report.
	auditSpan(t, "aws-bedrock-agents", "oneagent", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock-agents/oneagent"
| filter (gen_ai.provider.name == "aws_bedrock" or gen_ai.system == "aws_bedrock") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
