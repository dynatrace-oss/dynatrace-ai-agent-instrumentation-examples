package e2e

import (
	"testing"
)

func TestOpenAIOneAgent(t *testing.T) {
	startApp(t, "openai/oneagent")
	triggerHaiku(t, false)
	triggerHaikuGuardrailOpenAI(t)

	// triggerHaiku and triggerHaikuGuardrailOpenAI each produce their own trace.
	// sort + limit pins the baseline audit to the earlier (non-guardrail) trace
	// deterministically — otherwise which trace becomes the anchor is unspecified,
	// and a content-filtered trace is missing several baseline attributes (token
	// usage, response model), which would flip this audit's verdict independent of
	// any real regression.
	auditSpan(t, "openai", "oneagent", OpenAIProfile,
		`fetch spans, from: now()-10m
| filter service.name == "openai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)

	// The content-filter-tripping request is always sent last. Anchor on the
	// guardrail attribute itself rather than on span status: Azure rejects a
	// filtered prompt with BadRequestError (error span) but truncates a filtered
	// completion without one, and only a request the filter intervened on carries
	// the attribute at all.
	auditOpenAIGuardrailSpan(t, "openai", "oneagent",
		`fetch spans, from: now()-10m
| filter service.name == "openai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.guardrail.input.content) or isNotNull(gen_ai.guardrail.output.content)
| sort start_time desc
| limit 1`)
}
