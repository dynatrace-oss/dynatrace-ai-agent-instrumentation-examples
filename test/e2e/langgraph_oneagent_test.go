package e2e

import (
	"testing"
	"time"
)

// TestLangGraphOneAgent verifies OneAgent captures the LangGraph demo's
// LLM calls, including the input messages.
func TestLangGraphOneAgent(t *testing.T) {
	startApp(t, "langgraph/oneagent")

	runMakeTarget(t, "langgraph/oneagent", "request")

	// OneAgent fullstack ingestion into Grail lags further behind the request
	// than the OTLP path, so allow a longer window than the default.
	assertSpanExistsWithin(t, scopedDQL(`fetch spans
| filter service.name == "langgraph/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter contains(toString(`+"`gen_ai.input.messages`"+`), "cherry blossoms")
| sort timestamp desc
| limit 1`), 5*time.Minute)

	auditSpan(t, "langgraph", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langgraph/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.response.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
