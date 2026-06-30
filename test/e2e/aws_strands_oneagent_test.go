package e2e

import (
	"testing"
	"time"
)

func TestAWSStrandsOneAgent(t *testing.T) {
	startApp(t, "aws-strands/oneagent")
	// Give OneAgent extra time to complete instrumentation setup before the first
	// Bedrock call. In the consolidated nightly job this test runs after 6 other
	// oneagent suites on the same runner; without this delay spans are not captured.
	time.Sleep(10 * time.Second)
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
