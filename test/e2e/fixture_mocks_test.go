package e2e

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

// startOpenAICompatibleMock starts a local OpenAI-compatible stub and wires it
// into the test environment via the given env var names. Only active when
// apiKeyEnvVar is not already set — real-key CI runs pass through unmodified.
// Serves both /openai/v1/chat/completions and /v1/chat/completions so it works
// with SDKs that include the version prefix in their base URL (e.g. Groq) and
// those that do not (e.g. OpenAI-compatible clients pointing at a bare host).
// model is returned in the response body; set it to the value of MODEL or any
// sentinel string useful for asserting gen_ai.response.model in DT.
func startOpenAICompatibleMock(t *testing.T, apiKeyEnvVar, baseURLEnvVar string) {
	t.Helper()
	if os.Getenv(apiKeyEnvVar) != "" {
		return
	}
	handler := func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"id":      "chatcmpl-mock",
			"object":  "chat.completion",
			"created": 1700000000,
			"model":   os.Getenv("MODEL"),
			"choices": []map[string]interface{}{
				{
					"index": 0,
					"message": map[string]string{
						"role":    "assistant",
						"content": "Code flows like water\nBugs surface in morning light\nLogs reveal the truth",
					},
					"finish_reason": "stop",
				},
			},
			"usage": map[string]int{
				"prompt_tokens":     10,
				"completion_tokens": 20,
				"total_tokens":      30,
			},
		})
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/openai/v1/chat/completions", handler)
	mux.HandleFunc("/v1/chat/completions", handler)
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	t.Setenv(baseURLEnvVar, srv.URL)
	t.Setenv(apiKeyEnvVar, "mock-key-for-e2e")
}

// startCohereCompatibleMock starts a local Cohere v2 API stub and wires it
// into the test environment. Only active when COHERE_API_KEY is not already
// set — real-key CI runs pass through unmodified.
// The Cohere Python SDK reads CO_API_URL for the base URL override.
func startCohereCompatibleMock(t *testing.T) {
	t.Helper()
	if os.Getenv("COHERE_API_KEY") != "" {
		return
	}
	handler := func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"id": "chat-mock",
			"message": map[string]interface{}{
				"role": "assistant",
				"content": []map[string]interface{}{
					{"type": "text", "text": "Code flows like water\nBugs surface in morning light\nLogs reveal the truth"},
				},
			},
			"finish_reason": "COMPLETE",
			"usage": map[string]interface{}{
				"billed_units": map[string]int{"input_tokens": 10, "output_tokens": 20},
				"tokens":       map[string]int{"input_tokens": 10, "output_tokens": 20},
			},
			"model": os.Getenv("MODEL"),
		})
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/v2/chat", handler)
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	t.Setenv("CO_API_URL", srv.URL)
	t.Setenv("COHERE_API_KEY", "mock-key-for-e2e")
	t.Setenv("MODEL", "command-r-08-2024")
}

// startMistralCompatibleMock starts a local Mistral API stub and wires it into
// the test environment. Only active when MISTRAL_API_KEY is not already set —
// real-key CI runs pass through unmodified. The mistralai SDK posts to
// {server_url}/v1/chat/completions and returns an OpenAI-shaped body; the demo
// app reads MISTRAL_BASE_URL to override the base URL.
func startMistralCompatibleMock(t *testing.T) {
	t.Helper()
	if os.Getenv("MISTRAL_API_KEY") != "" {
		return
	}
	handler := func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"id":      "chatcmpl-mock",
			"object":  "chat.completion",
			"created": 1700000000,
			"model":   os.Getenv("MODEL"),
			"choices": []map[string]interface{}{
				{
					"index": 0,
					"message": map[string]string{
						"role":    "assistant",
						"content": "Code flows like water\nBugs surface in morning light\nLogs reveal the truth",
					},
					"finish_reason": "stop",
				},
			},
			"usage": map[string]int{
				"prompt_tokens":     10,
				"completion_tokens": 20,
				"total_tokens":      30,
			},
		})
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/chat/completions", handler)
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	t.Setenv("MISTRAL_BASE_URL", srv.URL)
	t.Setenv("MISTRAL_API_KEY", "mock-key-for-e2e")
	t.Setenv("MODEL", "mistral-small-latest")
}
