package e2e

import (
	"encoding/json"
	"encoding/pem"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// startFoundryAgentsMock starts a local HTTPS stub for the Foundry agents API
// (POST /agents/{name}/versions). Only active when AZURE_AI_PROJECT_ENDPOINT
// is unset. TLS is required because azure-core refuses bearer tokens over
// plain HTTP; the stub's certificate is trusted via REQUESTS_CA_BUNDLE.
func startFoundryAgentsMock(t *testing.T) {
	t.Helper()
	if os.Getenv("AZURE_AI_PROJECT_ENDPOINT") != "" {
		return
	}
	model := os.Getenv("MODEL")
	if model == "" {
		model = "gpt-4o-mini"
	}
	handler := func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || !strings.HasSuffix(r.URL.Path, "/versions") {
			http.NotFound(w, r)
			return
		}
		parts := strings.Split(strings.TrimSuffix(r.URL.Path, "/versions"), "/")
		name := parts[len(parts)-1]
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"object":     "agent.version",
			"id":         name + ":1",
			"name":       name,
			"version":    "1",
			"created_at": 1700000000,
			"metadata":   map[string]string{},
			"definition": map[string]interface{}{
				"kind":         "prompt",
				"model":        model,
				"instructions": "You are a haiku poet.",
			},
		})
	}
	srv := httptest.NewTLSServer(http.HandlerFunc(handler))
	t.Cleanup(srv.Close)

	caFile := filepath.Join(t.TempDir(), "foundry-mock-ca.pem")
	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: srv.Certificate().Raw})
	if err := os.WriteFile(caFile, certPEM, 0o600); err != nil {
		t.Fatalf("write mock CA: %v", err)
	}
	t.Setenv("REQUESTS_CA_BUNDLE", caFile)
	t.Setenv("AZURE_AI_PROJECT_ENDPOINT", srv.URL+"/api/projects/e2e")
	t.Setenv("FOUNDRY_STATIC_TOKEN", "mock-token-for-e2e")
	t.Setenv("MODEL", model)
}

func TestMicrosoftFoundryOneAgent(t *testing.T) {
	startFoundryAgentsMock(t)
	startApp(t, "microsoft-foundry/oneagent")
	triggerHaiku(t, true)

	auditSpan(t, "microsoft-foundry", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "microsoft-foundry/oneagent"
| filter gen_ai.provider.name == "microsoft.foundry"
| filter gen_ai.operation.name == "create_agent"
| filter dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.agent.name)
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(gen_ai.system_instructions)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`,
		"Backend mocked: in-process HTTPS stub serves the Foundry agents API via AZURE_AI_PROJECT_ENDPOINT. The OneAgent Foundry sensor instruments agent management calls only, so no token usage or message attributes are expected; gen_ai.system_instructions requires the Foundry prompt capture feature. Set AZURE_AI_PROJECT_ENDPOINT plus Entra ID credentials for live validation.")
}
