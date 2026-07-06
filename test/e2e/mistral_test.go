package e2e

import (
	"testing"
)

func TestMistralOneAgent(t *testing.T) {
	startApp(t, "mistral/oneagent")
	triggerHaiku(t, true)

	auditSpan(t, "mistral", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "mistral/oneagent"
| filter (isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)) and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
