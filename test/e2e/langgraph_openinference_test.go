package e2e

import (
	"testing"
)

func TestLangGraphOpenInference(t *testing.T) {
	startApp(t, "langgraph/openinference")
	makeRequest(t, "langgraph/openinference", "request")

	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "langgraph/openinference"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(gen_ai.tool.definitions)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`),
		[]string{"gen_ai.response.finish_reasons", "gen_ai.tool.definitions", "gen_ai.conversation.id"}, nil)

	assertSpanWithAttrs(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "langgraph/openinference"
| filter gen_ai.tool.name == "get_haiku_inspiration"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`),
		[]string{"gen_ai.tool.name", "gen_ai.tool.call.id", "gen_ai.conversation.id"}, nil)

	auditSpanWithMetrics(t, "langgraph", "openinference", AzureProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langgraph/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"langgraph/openinference", genAIClientMetrics)
}
