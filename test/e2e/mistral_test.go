package e2e

import (
	"testing"
)

func TestMistralOneAgent(t *testing.T) {
	startMistralCompatibleMock(t)
	startApp(t, "mistral/oneagent")
	triggerHaiku(t, false)

	auditSpan(t, "mistral", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "mistral/oneagent"
| filter (isNotNull(gen_ai.provider.name) or isNotNull(gen_ai.system)) and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"Backend mocked: in-process httptest stub intercepts Mistral SDK calls via MISTRAL_BASE_URL. Replace with a real MISTRAL_API_KEY secret for live validation.")
}
