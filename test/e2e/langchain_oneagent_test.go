package e2e

import (
	"testing"
	"time"
)

// TestLangChainOneAgent verifies that OneAgent's google-genai sensor reports
// model and token usage for Gemini calls made through LangChain's
// ChatGoogleGenerativeAI. The LangChain sensor alone only records structure,
// so these attributes come from the provider sensor.
func TestLangChainOneAgent(t *testing.T) {
	startApp(t, "langchain/oneagent")
	runMakeTarget(t, "langchain/oneagent", "request")

	const llmSpan = `fetch spans, from: now()-10m
| filter service.name == "langchain/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter contains(toString(gen_ai.request.model), "gemini") or contains(toString(gen_ai.response.model), "gemini")
| filter isNotNull(gen_ai.usage.input_tokens) and isNotNull(gen_ai.usage.output_tokens)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`

	// OneAgent ingestion lags the OTLP path; allow a longer first poll.
	assertSpanExistsWithin(t, scopedDQL(llmSpan), 5*time.Minute)

	auditSpan(t, "langchain", "oneagent", GenericProfile, llmSpan)
}
