package e2e

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"testing"
)

const (
	adkZeroCodeApp     = "academic_research"
	adkZeroCodeService = "google-adk-zero-code"
)

// triggerADKAPIServer drives ADK's own API server: create a session, then POST
// /run. Kept local to this suite rather than added to fixture_triggers_test.go,
// which is shared infrastructure and would make every PR run the full matrix.
func triggerADKAPIServer(t *testing.T) {
	t.Helper()
	const base = "http://127.0.0.1:8000"

	post := func(url string, body any) {
		b, _ := json.Marshal(body)
		resp, err := http.Post(url, "application/json", bytes.NewReader(b))
		if err != nil {
			t.Fatalf("POST %s: %v", url, err)
		}
		defer resp.Body.Close()
		if resp.StatusCode >= 300 {
			rb, _ := io.ReadAll(resp.Body)
			t.Fatalf("POST %s returned %d: %s", url, resp.StatusCode, rb)
		}
	}

	post(base+"/apps/"+adkZeroCodeApp+"/users/e2e/sessions", map[string]any{
		"session_id": "e2e-session",
		"state":      map[string]string{"seminal_paper": "Attention is All You Need"},
	})

	// The coordinator's value is delegation, and asking only for a summary of a
	// well-known paper lets the model answer from its own weights, producing a
	// trace with no execute_tool span. Asking for recent citing work forces the
	// websearch tool onto the happy path.
	post(base+"/run", map[string]any{
		"app_name":   adkZeroCodeApp,
		"user_id":    "e2e",
		"session_id": "e2e-session",
		"new_message": map[string]any{
			"role": "user",
			"parts": []map[string]string{{
				"text": "Summarize the key contributions of the paper: Attention is All You Need. " +
					"Then use your tools to find recent papers citing it and to suggest future " +
					"research directions based on what you find.",
			}},
		},
	})
}

func TestGoogleADKZeroCode(t *testing.T) {
	// No OTel code and no web code in this demo: it ships an agent package and
	// runs ADK's own `adk api_server` under opentelemetry-instrument, which
	// builds the SDK providers from OTEL_* env vars before the server starts.
	// Instrumentation is therefore deployment config (a Dockerfile CMD and a set
	// of environment variables) rather than a source change per agent, which is
	// how it scales across many agents.
	//
	// make run-collector routes the app through a local OTel Collector, which
	// repairs the two gaps ADK leaves. ADK splits the GenAI semantics over two
	// nested spans per LLM call: provider and token counts on call_llm, message
	// content and gen_ai.operation.name on the child "generate_content <model>"
	// span. Every GenAI view in the app admits a span only if gen_ai.system or
	// gen_ai.provider.name is set, and the Prompts stream then drops rows with no
	// input and no output, so on a direct export call_llm passes the first gate
	// and fails the second while generate_content does the reverse: spans reach
	// Distributed Tracing but no prompt is ever displayed. The collector sets
	// gen_ai.provider.name = "vertexai" on the content-bearing span, strips ADK's
	// scope name off call_llm (both gen_ai.system and gen_ai.provider.name carry
	// it, and the app resolves the provider as coalesce of the two, so leaving
	// either one in place keeps call_llm's duplicate token counts inside every
	// aggregate), and mirrors gen_ai.response.model from the request model.
	startAppWithTarget(t, "google-adk/zero-code", "run-collector")
	triggerADKAPIServer(t)

	// Two span_metrics connectors derive gen_ai.invoke_agent.duration and
	// gen_ai.execute_tool.duration from ADK's own invoke_agent / execute_tool
	// spans, which ADK records only under its own pre-semconv metric names.
	//
	// gen_ai.execute_tool.duration depends on the coordinator actually delegating
	// to an AgentTool. The request in triggerADKAPIServer asks for recent citing
	// work, which it cannot answer without the websearch tool; a request that
	// only asks for a summary lets the model answer from its weights and produces
	// a trace with no execute_tool span at all.
	//
	// gen_ai.invoke_workflow.duration is absent by design: ADK only opens an
	// invoke_workflow span for a google.adk.workflow.Workflow node, and this demo
	// is an LlmAgent with AgentTool sub-agents.
	metrics := append(append([]string{}, genAIClientMetrics...), genAIAgentDurationMetrics...)

	auditSpanWithMetrics(t, "google-adk", "zero-code", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "`+adkZeroCodeService+`"
| filter gen_ai.provider.name == "vertexai"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		adkZeroCodeService, metrics)

	// Regression guard for the split above: a span must satisfy the app's GenAI
	// gate and carry message content at the same time, which is what makes the
	// Prompts view populate. Asserting the two conditions on separate spans would
	// pass on a raw ADK export and still show an empty view.
	assertSpanExists(t, `fetch spans, from: now()-10m
| filter service.name == "`+adkZeroCodeService+`"
| filter isNotNull(gen_ai.system) or isNotNull(gen_ai.provider.name)
| filter isNotNull(gen_ai.input.messages) and isNotNull(gen_ai.output.messages)
| limit 1`)

	// call_llm must no longer pass the app's gate. It carries a duplicate copy of
	// the token counts, so if it does, every token and LLM request is counted
	// twice and the provider list gains an entity named "gcp.vertex.agent".
	assertNoMatchingSpan(t, `fetch spans, from: now()-10m
| filter service.name == "`+adkZeroCodeService+`"
| filter span.name == "call_llm"
| filter isNotNull(gen_ai.system) or isNotNull(gen_ai.provider.name)
| limit 1`)

	// Every span ADK emits is span.kind=internal, so nothing in ADK's own output
	// lets SDv2 detect a service. `adk api_server` serves a FastAPI app, so the
	// opentelemetry-instrumentation-fastapi package that opentelemetry-instrument
	// loads produces a genuine SERVER span at the HTTP entry point without any
	// span-kind rewriting.
	assertSpanExists(t, `fetch spans, from: now()-10m
| filter service.name == "`+adkZeroCodeService+`"
| filter span.kind == "server"
| limit 1`)
}
