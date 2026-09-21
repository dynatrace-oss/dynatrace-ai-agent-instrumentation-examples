package e2e

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"fmt"
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

// startAnthropicCompatibleMock starts a local Anthropic Messages API stub and
// points Claude Code at it. It is enabled only when neither supported real CI
// credential is present, so nightly/manual runs can still validate Anthropic.
func startAnthropicCompatibleMock(t *testing.T) {
	t.Helper()
	if os.Getenv("ANTHROPIC_API_KEY") != "" || os.Getenv("CLAUDE_CODE_OAUTH_TOKEN") != "" {
		return
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/v1/messages/count_tokens", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]int{"input_tokens": 10})
	})
	mux.HandleFunc("/v1/messages", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
        w.Header().Set("request-id", "req_claude_code_e2e")
		var request struct {
			Model  string `json:"model"`
			Stream bool   `json:"stream"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			http.Error(w, `{"type":"error","error":{"type":"invalid_request_error","message":"invalid JSON"}}`, http.StatusBadRequest)
			return
		}
		if request.Model == "" {
			request.Model = "claude-sonnet-4-5-20250929"
		}

		if !request.Stream {
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"id": "msg_claude_code_e2e", "type": "message", "role": "assistant",
				"model": request.Model, "stop_reason": "end_turn", "stop_sequence": nil,
				"content": []map[string]string{{"type": "text", "text": "claude-code-e2e-ok"}},
				"usage": map[string]int{"input_tokens": 10, "output_tokens": 8},
			})
			return
		}

		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "streaming unsupported", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.WriteHeader(http.StatusOK)

		events := []struct {
			name string
			data string
		}{
			{"message_start", fmt.Sprintf(`{"type":"message_start","message":{"id":"msg_claude_code_e2e","type":"message","role":"assistant","content":[],"model":%q,"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":10,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0}}}`, request.Model)},
			{"content_block_start", `{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}`},
			{"content_block_delta", `{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"claude-code-e2e-ok"}}`},
			{"content_block_stop", `{"type":"content_block_stop","index":0}`},
			{"message_delta", `{"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":8}}`},
			{"message_stop", `{"type":"message_stop"}`},
		}
		for _, event := range events {
			_, _ = fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event.name, event.data)
			flusher.Flush()
		}
	})

	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	t.Setenv("ANTHROPIC_BASE_URL", srv.URL)
	t.Setenv("ANTHROPIC_API_KEY", "mock-key-for-e2e")
	t.Setenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
}
