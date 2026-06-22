package e2e

import (
	"testing"
)

func TestAnthropicOneAgent(t *testing.T) {
	startApp(t, "anthropic/oneagent")
	triggerHaiku(t, true)

	// The Anthropic SDK routes through AWS Bedrock (AnthropicBedrock client).
	// Tests run sequentially in CI; sort desc so the most-recent span wins
	// in case earlier bedrock-test spans are still within the 10-minute window.
	auditSpan(t, "anthropic", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter gen_ai.provider.name == "aws_bedrock" and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
