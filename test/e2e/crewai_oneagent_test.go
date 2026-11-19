package e2e

import (
	"testing"
	"time"
)

// TestCrewAIOneAgent verifies OneAgent alone captures the CrewAI demo through
// the CrewAI sensor: the workflow, task and agent spans of a crew run, and a
// shared gen_ai.conversation.id across the turns of one conversational Flow.
//
// Needs the "Experimental Python GenAI CrewAI [Opt-In]" OneAgent feature
// (OneAgent 1.339+). The OpenAI sensor features are not relied on, so no chat
// span, prompt or guardrail assertions are made. Runs against real Azure
// OpenAI, no mock.
func TestCrewAIOneAgent(t *testing.T) {
	startApp(t, "crewai/oneagent")

	runMakeTarget(t, "crewai/oneagent", "request")
	runMakeTarget(t, "crewai/oneagent", "request-chat")

	const base = `fetch spans
| filter service.name == "crewai/oneagent"
| filter dt.openpipeline.source == "oneagent"
`

	// OneAgent ingestion into Grail lags the request, so allow a long window.
	// 1. workflow span (Crew.kickoff) with token usage
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "workflow"
| filter isNotNull(gen_ai.usage.input_tokens)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 2. task span
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "task"
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 3. agent span
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "agent"
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 4. both /chat turns carry the session id as gen_ai.conversation.id.
	// Provisional until CI shows which spans carry it (design, Open Questions).
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.conversation.id == "e2e-session"
| summarize traces = countDistinct(trace.id)
| filter traces >= 2`), 5*time.Minute)
}
