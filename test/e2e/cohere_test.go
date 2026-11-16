package e2e

import (
	"testing"
	"time"
)

func TestCohereOneAgent(t *testing.T) {
	startCohereCompatibleMock(t)
	startApp(t, "cohere/oneagent")
	triggerHaiku(t, false)

	// Requires the opt-in OneAgent prompt capture feature for this sensor.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "cohere/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.input.messages) and isNotNull(gen_ai.output.messages)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	auditSpan(t, "cohere", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "cohere/oneagent"
| filter gen_ai.provider.name == "cohere" or gen_ai.system == "cohere"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"Backend mocked: in-process httptest stub intercepts Cohere SDK calls via CO_API_URL. Replace with a real COHERE_API_KEY secret for live validation.")
}
