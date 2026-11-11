package e2e

import (
	"testing"
	"time"
)

func TestMistralOneAgent(t *testing.T) {
	startMistralCompatibleMock(t)
	startApp(t, "mistral/oneagent")
	triggerHaiku(t, false)

	// Requires the opt-in OneAgent prompt capture feature for this sensor.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "mistral/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.input.messages) and isNotNull(gen_ai.output.messages)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	auditSpan(t, "mistral", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "mistral/oneagent"
| filter (gen_ai.provider.name == "mistralai" or gen_ai.system == "mistralai") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"Backend mocked: in-process httptest stub intercepts Mistral SDK calls via MISTRAL_BASE_URL. Replace with a real MISTRAL_API_KEY secret for live validation.")
}
