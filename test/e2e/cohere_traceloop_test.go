package e2e

import (
	"testing"
)

func TestCohereTraceloop(t *testing.T) {
	startCohereCompatibleMock(t)
	startApp(t, "cohere/traceloop")
	triggerHaiku(t, false)

	// Traceloop instruments Cohere via the OpenLLMetry CohereInstrumentor.
	// The OneAgent Python GenAI Cohere sensor must be DISABLED so that the
	// suppression mechanism does not drop the Traceloop spans; OneAgent's OTel
	// sensor then picks them up and nests them into the PurePath.
	// Unlike the OneAgent-only path, Traceloop also captures gen_ai.input.messages
	// and gen_ai.output.messages (prompt/response content).
	auditSpan(t, "cohere", "traceloop", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "cohere-traceloop"
| filter gen_ai.system == "Cohere"
| filter isNotNull(gen_ai.request.model)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"Backend mocked: in-process httptest stub intercepts Cohere SDK calls via CO_API_URL. Replace with a real COHERE_API_KEY secret for live validation. Requires the Python GenAI Cohere OneAgent feature flag to be DISABLED.")
}
