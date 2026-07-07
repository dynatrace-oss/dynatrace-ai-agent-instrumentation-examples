package e2e

import (
	"testing"
)

func TestAWSStrandsOneAgent(t *testing.T) {
	startApp(t, "aws-strands/oneagent")
	triggerAgent(t)

	// gen_ai.bedrock.guardrail.* (AR-017/AR-018/AR-019) are not emitted
	// because the demo does not configure Bedrock guardrails — expected FAIL in report.
	auditSpan(t, "aws-strands", "oneagent", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-strands/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| limit 1`)
}
