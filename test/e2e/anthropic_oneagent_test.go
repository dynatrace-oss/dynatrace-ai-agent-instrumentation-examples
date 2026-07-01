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
| filter gen_ai.provider.name == "anthropic" and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
