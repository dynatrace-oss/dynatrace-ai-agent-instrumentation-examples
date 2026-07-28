package e2e

import (
	"testing"
)

func TestAWSBedrockOpenInference(t *testing.T) {
	startApp(t, "aws-bedrock/openinference")
	triggerHaiku(t, true)
	triggerHaikuGuardrail(t)

	// triggerHaiku and triggerHaikuGuardrail each produce their own trace.
	// sort + limit pins the baseline audit to the earlier (non-guardrail)
	// trace deterministically — otherwise which trace becomes the anchor is
	// unspecified, and the guardrail-blocked trace is missing several
	// baseline attributes (e.g. token usage), which would flip this audit's
	// verdict independent of any real regression.
	auditSpan(t, "aws-bedrock", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/openinference"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)

	// The guardrail-triggering request is always sent last, so the latest
	// matching span is the one that actually tripped the guardrail.
	auditGuardrailSpan(t, "aws-bedrock", "openinference",
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/openinference"
| filter isNotNull(gen_ai.request.model)
| sort start_time desc
| limit 1`)
}
