package e2e

import (
	"testing"
)

func TestAnthropicOneAgent(t *testing.T) {
	startApp(t, "anthropic/oneagent")
	triggerHaiku(t, true)

	auditSpan(t, "anthropic", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "anthropic/oneagent"
| filter gen_ai.provider.name == "aws_bedrock" and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
