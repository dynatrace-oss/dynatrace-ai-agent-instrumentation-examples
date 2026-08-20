package e2e

import (
	"testing"
)

func TestAWSStrandsOpenInference(t *testing.T) {
	startCLIApp(t, "aws-strands/openinference")

	// StrandsAgentsToOpenInferenceProcessor (openinference-instrumentation-strands-agents)
	// mutates each span in-place to add OpenInference llm.*/tool.*/agent.* attributes, but
	// does not remove the gen_ai.* attributes Strands already emits natively. So the spans
	// exported here carry both attribute sets, and the collector's transform/strands
	// processor normalizes Strands' own gen_ai.* naming quirks exactly as it does for the
	// plain aws-strands/opentelemetry demo — no OpenInference-specific mapping is needed
	// because gen_ai.* was never replaced. See the README's "Known gaps & limitations".
	//
	// gen_ai.bedrock.guardrail.* (AR-017/AR-018/AR-019) are not emitted because the demo
	// does not configure Bedrock guardrails — expected FAIL in report.
	metrics := append(append([]string{}, genAIClientMetrics...), genAIAgentDurationMetrics...)

	auditSpanWithMetrics(t, "aws-strands", "openinference", BedrockProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-strands/openinference"
| filter isNotNull(gen_ai.provider.name)
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`,
		"aws-strands/openinference", metrics)
}
