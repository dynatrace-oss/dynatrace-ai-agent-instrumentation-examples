package e2e

import (
	"testing"
	"time"
)

// TestGoogleADKOneAgent verifies OneAgent's Google ADK sensor captures the
// demo's LLM call with the request model and input messages.
func TestGoogleADKOneAgent(t *testing.T) {
	startApp(t, "google-adk/oneagent")

	runMakeTarget(t, "google-adk/oneagent", "request")

	// OneAgent fullstack ingestion into Grail lags further behind the request
	// than the OTLP path, so allow a longer window than the default.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans
| filter service.name == "google-adk/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter gen_ai.operation.name == "chat"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	auditSpan(t, "google-adk", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "google-adk/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter gen_ai.operation.name == "chat"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
