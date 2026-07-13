package e2e

import (
	"testing"
)

func TestAWSBedrockAgentsOneAgent(t *testing.T) {
	startCLIApp(t, "aws-bedrock-agents/oneagent")

	// gen_ai.bedrock.guardrail.* (AR-017/AR-018/AR-019) are not emitted
	// because the demo does not configure Bedrock guardrails — expected FAIL in report.
	auditSpan(t, "aws-bedrock-agents", "oneagent", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock-agents/oneagent"
| filter isNotNull(gen_ai.system)
| limit 1`)
}
