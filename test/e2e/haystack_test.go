package e2e

import (
	"testing"
)

func TestHaystackOneAgent(t *testing.T) {
	startApp(t, "haystack/oneagent")
	triggerHaiku(t, false)

	auditSpan(t, "haystack", "oneagent", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "haystack/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"gen_ai.system expected to be az.ai.openai — OneAgent instruments the underlying openai SDK calls made by AzureOpenAIGenerator; confirm with ICP-6026.")
}
