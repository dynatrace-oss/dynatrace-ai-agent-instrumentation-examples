package e2e

import (
	"testing"
)

func TestAWSBedrockOpenInference(t *testing.T) {
	startApp(t, "aws-bedrock/openinference")
	triggerHaiku(t, true)
	triggerHaikuGuardrail(t)
	triggerApplyGuardrail(t)

	// triggerHaiku and triggerHaikuGuardrail each produce their own trace.
	// sort + limit pins the baseline audit to the earlier (non-guardrail)
	// trace deterministically — otherwise which trace becomes the anchor is
	// unspecified, and the guardrail-blocked trace is missing several
	// baseline attributes (e.g. token usage), which would flip this audit's
	// verdict independent of any real regression.
	auditSpanWithMetrics(t, "aws-bedrock", "openinference", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/openinference"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`,
		"aws-bedrock/openinference", genAIClientMetrics)

	// The guardrail-triggering request is always sent last, so the latest
	// matching span is the one that actually tripped the guardrail. Metrics are
	// service-scoped and include data from the non-guardrail request above.
	auditSpanWithMetrics(t, "aws-bedrock", "openinference-guardrail", GuardrailProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/openinference"
| filter isNotNull(gen_ai.request.model)
| sort start_time desc
| limit 1`,
		"aws-bedrock/openinference", genAIClientMetrics)

	// triggerApplyGuardrail's two calls (safe, then trigger) each produce their
	// own GUARDRAIL-kind span; sort + limit pins this audit to the later
	// (triggering) one deterministically.
	auditApplyGuardrailSpan(t, "aws-bedrock", "openinference",
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock/openinference"
| filter gen_ai.operation.name == "GUARDRAIL"
| sort start_time desc
| limit 1`)
}
