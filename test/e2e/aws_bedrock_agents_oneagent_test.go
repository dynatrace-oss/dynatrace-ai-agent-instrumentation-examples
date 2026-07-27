package e2e

import (
	"testing"
)

func TestAWSBedrockAgentsOneAgent(t *testing.T) {
	startApp(t, "aws-bedrock-agents/oneagent")
	triggerAgent(t)
	triggerAgentGuardrail(t)

	auditSpan(t, "aws-bedrock-agents", "oneagent", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock-agents/oneagent"
| filter (gen_ai.provider.name == "aws_bedrock") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
