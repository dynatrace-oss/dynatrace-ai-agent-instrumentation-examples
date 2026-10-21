package e2e

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestAnthropicOpenInferenceResponseModelMapping(t *testing.T) {
	for _, tc := range []struct {
		file    string
		mapping string
	}{
		{
			file:    "otel-collector-config.yaml",
			mapping: `set(attributes["gen_ai.response.model"], attributes["llm.response.model_name"]) where attributes["llm.response.model_name"] != nil and attributes["gen_ai.response.model"] == nil`,
		},
		{
			file:    "openpipeline-openinference.yaml",
			mapping: `fieldsAdd gen_ai.response.model = llm.response.model_name,`,
		},
	} {
		t.Run(tc.file, func(t *testing.T) {
			config, err := os.ReadFile(filepath.Join(repoRoot(), "anthropic", "openinference", tc.file))
			if err != nil {
				t.Fatal(err)
			}
			if !strings.Contains(string(config), tc.mapping) {
				t.Error("response model must be mapped from llm.response.model_name, not the request model")
			}
		})
	}
}

func TestAnthropicOpenInference(t *testing.T) {
	// CLI app: make run starts the OTel Collector (Docker) then runs app.py once.
	// No triggerHaiku — the haiku request is issued by make run itself.
	startCLIApp(t, "anthropic/openinference")

	auditSpanWithMetrics(t, "anthropic", "openinference", AnthropicProfile,
		`fetch spans, from: now()-10m
| filter service.name == "anthropic/openinference"
| filter isNotNull(gen_ai.request.model)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`,
		"anthropic/openinference", genAIClientMetrics)
}
