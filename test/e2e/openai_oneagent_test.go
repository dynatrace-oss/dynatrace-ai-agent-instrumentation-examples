package e2e

import (
	"testing"
)

func TestOpenAIOneAgent(t *testing.T) {
	startApp(t, "openai/oneagent")
	triggerHaiku(t, false)
	makeRequest(t, "openai/oneagent", "request-trigger-guardrail")

	// triggerHaiku and request-trigger-guardrail each produce their own trace.
	// sort + limit pins the baseline audit to the earlier (non-guardrail) trace
	// deterministically — the jailbreak trace may be missing token usage
	// attributes when the request is blocked, which would skew the audit.
	auditSpan(t, "openai", "oneagent", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)

	// The jailbreak request is always sent last, so the latest matching span is
	// the one with prompt_filter_results populated (AR-015).
	auditSpan(t, "openai", "oneagent-guardrail", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort start_time desc
| limit 1`)
}
