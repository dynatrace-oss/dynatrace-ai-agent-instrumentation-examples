package e2e

import (
	"os"
	"testing"
)

func TestGroqOneAgent(t *testing.T) {
	if os.Getenv("GROQ_API_KEY") == "" {
		// No real key — point the Groq SDK at a local Ollama instance.
		// Ollama serves an OpenAI-compatible API at /v1, which aligns with
		// the Groq SDK's base-URL override (GROQ_BASE_URL replaces the full
		// https://api.groq.com/openai/v1 default).
		// In CI the ollama_model matrix field triggers install + model pull.
		t.Setenv("GROQ_API_KEY", "ollama-stub")
		t.Setenv("GROQ_BASE_URL", "http://localhost:11434/v1")
	}
	startApp(t, "groq/oneagent")
	triggerHaiku(t, false)

	// TODO: confirm gen_ai.system / gen_ai.provider.name emitted by OneAgent
	// for the Groq SDK and tighten the provider filter once span metadata is known.
	auditSpan(t, "groq", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "groq/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`)
}
