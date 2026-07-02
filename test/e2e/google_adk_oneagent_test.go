package e2e

import (
	"testing"
)

func TestGoogleADKOneAgent(t *testing.T) {
	startApp(t, "google-adk/oneagent")
	triggerResearch(t)

	auditSpan(t, "google-adk", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk/oneagent"
| filter gen_ai.system == "gemini" and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
