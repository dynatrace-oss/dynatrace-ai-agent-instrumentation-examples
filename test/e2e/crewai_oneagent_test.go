package e2e

import (
	"testing"
	"time"
)

// TestCrewAIOneAgent verifies OneAgent alone captures the CrewAI demo through
// the CrewAI sensor: the workflow, task and agent spans of a crew run, and one
// workflow span per turn of a conversational Flow.
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

	// 4. each of the two /chat turns produces a workflow span for the Flow, in
	// its own trace. The sensor sets no conversation id, so turns are linked
	// only by the app's session_id, not by a span attribute.
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "workflow"
| filter gen_ai.agent.name == "ChatFlow"
| summarize traces = countDistinct(trace.id)
| filter traces >= 2`), 5*time.Minute)
}
