package e2e

import (
	"testing"
	"time"
)

// TestCrewAIOneAgent verifies OneAgent alone captures the CrewAI demo:
// the CrewAI sensor's workflow, task and agent spans, the OpenAI sensor's chat
// span (with input messages) under them, and the Azure content-filter
// guardrail attributes on a CrewAI-issued call.
//
// Needs four OneAgent features (OneAgent 1.339+ for the CrewAI one):
// Experimental Python GenAI CrewAI, Python GenAI OpenAI, OpenAI prompt capture
// and OpenAI guardrails capture. Runs against real Azure OpenAI, no mock.
func TestCrewAIOneAgent(t *testing.T) {
	startApp(t, "crewai/oneagent")

	runMakeTarget(t, "crewai/oneagent", "request")
	triggerHaikuGuardrailOpenAI(t)

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

	// 4. chat span from the OpenAI sensor, with captured input messages
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.name == "chat"
| filter contains(toString(`+"`gen_ai.input.messages`"+`), "cherry blossoms")
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// Earliest non-error chat span, so the guardrail trace never becomes the anchor.
	// GenericProfile, not AzureProfile: OneAgent never emits the OTel-path
	// gen_ai.prompt.prompt_filter_results / completion.content_filter_results
	// that AzureProfile requires (guardrails are audited separately below).
	auditSpan(t, "crewai", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "crewai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter gen_ai.operation.name == "chat"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)

	// Anchor on the guardrail attribute rather than span status or count.
	auditOpenAIGuardrailSpan(t, "crewai", "oneagent",
		`fetch spans, from: now()-10m
| filter service.name == "crewai/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.guardrail.input.content) or isNotNull(gen_ai.guardrail.output.content)
| sort start_time desc
| limit 1`)
}
