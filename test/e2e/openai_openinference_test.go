package e2e

import (
	"testing"
)

func TestOpenAIOpenInference(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startCLIApp(t, "openai/openinference")

	// TEMPORARY: drop the gen_ai.operation.name optional check (AR-008) to
	// exercise the new PR attribute-diff feature against the nightly
	// baseline on main. Revert before merging.
	profile := OpenAIProfile
	var optional []AttributeCheck
	for _, c := range profile.Optional {
		if c.RuleID != "AR-008" {
			optional = append(optional, c)
		}
	}
	profile.Optional = optional

	auditSpanWithMetrics(t, "openai", "openinference", profile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"openai/openinference", genAIClientMetrics)
}
