package e2e

import (
	"testing"
	"time"
)

// TestCrewAIOneAgent verifies OneAgent alone captures the CrewAI demo through
// the CrewAI sensor: the workflow, task and agent spans of a crew run, for a
// single request and for each turn of a two-turn chat. It then audits those
// attributes against CrewAIOneAgentProfile.
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

	// 2. task span, named after the agent's role, with the agent's model
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "task"
| filter gen_ai.agent.name == "Poet"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 3. agent span, named after the agent's role, with the agent's model
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "agent"
| filter gen_ai.agent.name == "Poet"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 4. the single request and both chat turns each ran the crew, so there are
	// at least three traces with a workflow span. The sensor sets no conversation
	// id, so chat turns are linked only by the app's session_id, not by a span
	// attribute.
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "workflow"
| filter isNotNull(gen_ai.usage.input_tokens)
| summarize traces = countDistinct(trace.id)
| filter traces >= 3`), 5*time.Minute)

	// Audit the CrewAI sensor's own attributes on the earliest crew run (the
	// /haiku request), merged over its trace. CrewAIOneAgentProfile leaves out the
	// chat-span attributes, which come from the optional OpenAI sensor.
	auditSpan(t, "crewai", "oneagent", CrewAIOneAgentProfile,
		`fetch spans, from: now()-10m
| filter service.name == "crewai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter gen_ai.operation.kind == "workflow"
| filter isNotNull(gen_ai.usage.input_tokens)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)
}
