package e2e

import (
	"testing"
)

func TestLangGraphOneAgent(t *testing.T) {
	startApp(t, "langgraph/oneagent")
	triggerHaiku(t, true)

	auditSpan(t, "langgraph", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langgraph/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
