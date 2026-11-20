package e2e

import (
	"testing"
	"time"
)

// TestLangChainOneAgent verifies what OneAgent alone captures from the
// agentic-RAG haiku workflow in langchain/oneagent, on real Gemini traffic:
//
//   - the LangChain sensor's workflow, task, agent, tool and retrieval spans
//     (gen_ai.operation.kind), which only carry structure;
//   - the Google GenAI sensor's chat span (model and token usage) and its
//     embeddings span for the retriever's query embedding.
//
// The kinds are asserted, plus that one trace holds all of them. Parent span
// ids are not asserted: how OneAgent parents provider spans under framework
// spans is not documented. The chat span is audited against GenericProfile and
// the workflow trace against LangChainOneAgentProfile.
//
// Needs the OneAgent Python LangChain sensor (opt-in, OneAgent 1.333+) and the
// experimental, opt-in Google GenAI sensor. The Claude path of the example is not asserted, since
// CI only provides GOOGLE_API_KEY.
func TestLangChainOneAgent(t *testing.T) {
	startApp(t, "langchain/oneagent")
	runMakeTarget(t, "langchain/oneagent", "request")

	const base = `fetch spans, from: now()-10m
| filter service.name == "langchain/oneagent"
| filter dt.openpipeline.source == "oneagent"
`

	const llmSpan = base + `| filter contains(toString(gen_ai.request.model), "gemini") or contains(toString(gen_ai.response.model), "gemini")
| filter isNotNull(gen_ai.usage.input_tokens) and isNotNull(gen_ai.usage.output_tokens)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`

	// OneAgent ingestion lags the OTLP path; allow a longer first poll.
	// 1. Gemini chat span from the Google GenAI sensor, with model and tokens.
	assertSpanExistsWithin(t, scopedDQL(llmSpan), 5*time.Minute)

	auditSpan(t, "langchain", "oneagent", GenericProfile, llmSpan)

	// 2. workflow: the root chain. Framework spans carry no operation name.
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "workflow"
| filter isNull(gen_ai.operation.name)
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 3. task: a nested chain (prompt template, output parser).
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "task"
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 4. tool: the model's call to search_haiku_guide.
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "tool"
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 5. retrieval: the retriever invoked by the tool.
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.kind == "retrieval"
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 6. embeddings from the Google GenAI sensor. Gemini embeddings return no
	// token usage, so there is no token filter. The index built at startup
	// could satisfy this alone; the query-time embedding is asserted in 7.
	assertSpanExistsWithin(t, scopedDQL(base+`| filter gen_ai.operation.name == "embeddings"
| filter contains(toString(gen_ai.request.model), "gemini") or contains(toString(gen_ai.response.model), "gemini")
| sort timestamp desc
| limit 1`), 5*time.Minute)

	// 7. One trace holds the whole flow: a workflow, a tool, a retrieval, an
	// embeddings span and the two model-call (agent) spans. The trailing filter
	// makes the poll keep waiting until every span of the trace is ingested,
	// instead of failing on a partial trace.
	assertSpanExistsWithin(t, scopedDQL(base+`| summarize
    workflow = countIf(gen_ai.operation.kind == "workflow"),
    tool = countIf(gen_ai.operation.kind == "tool"),
    retrieval = countIf(gen_ai.operation.kind == "retrieval"),
    embeddings = countIf(gen_ai.operation.name == "embeddings"),
    agent = countIf(gen_ai.operation.kind == "agent"),
    by: {trace.id}
| filter workflow >= 1 and tool >= 1 and retrieval >= 1 and embeddings >= 1 and agent >= 2
| limit 1`), 5*time.Minute)

	// 8. Audit the LangChain sensor's own attributes on the earliest workflow,
	// merged over its trace. LangChainOneAgentProfile leaves out the model and
	// token attributes, which belong to the provider sensor's chat span.
	auditSpan(t, "langchain", "oneagent", LangChainOneAgentProfile,
		`fetch spans, from: now()-10m
| filter service.name == "langchain/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter gen_ai.operation.kind == "workflow"
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)
}
