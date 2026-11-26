package e2e

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
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
			"service_tier": "on_demand",
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
	mux.HandleFunc("/chat/completions", handler) // Together AI: base URL already includes /v1
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	t.Setenv(baseURLEnvVar, srv.URL)
	t.Setenv(apiKeyEnvVar, "mock-key-for-e2e")
	tagMockTraffic(t)
}

// tagMockTraffic marks spans from apps started after this call as mock traffic
// (deployment.environment.name=ci-mock) so the tenant can filter them out.
func tagMockTraffic(t *testing.T) {
	t.Helper()
	attrs := "deployment.environment.name=ci-mock"
	if existing := os.Getenv("OTEL_RESOURCE_ATTRIBUTES"); existing != "" {
		attrs = existing + "," + attrs
	}
	t.Setenv("OTEL_RESOURCE_ATTRIBUTES", attrs)
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
//
// The stub decides by request content, not by call count:
//   - any message holds a tool_result block (the follow-up): text reply
//   - the request declares a Read tool and has no tool_result yet: a tool turn
//     with two tool_use blocks (Read on the example README, and Bash echo), so a
//     run exercises one allowed and one denied permission check
//   - anything else: text reply
func startAnthropicCompatibleMock(t *testing.T) {
	t.Helper()
	if os.Getenv("ANTHROPIC_API_KEY") != "" || os.Getenv("CLAUDE_CODE_OAUTH_TOKEN") != "" {
		return
	}
	tagMockTraffic(t)

	readPath := filepath.Join(repoRoot(), "ai-coding-agents/claude-code/README.md")
	type toolUse struct {
		id    string
		name  string
		input map[string]interface{}
	}
	toolTurn := []toolUse{
		{"toolu_e2e_read", "Read", map[string]interface{}{"file_path": readPath}},
		{"toolu_e2e_bash", "Bash", map[string]interface{}{"command": "echo claude-code-e2e", "description": "Print a marker"}},
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
			Tools  []struct {
				Name string `json:"name"`
			} `json:"tools"`
			Messages []struct {
				Role    string          `json:"role"`
				Content json.RawMessage `json:"content"`
			} `json:"messages"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			http.Error(w, `{"type":"error","error":{"type":"invalid_request_error","message":"invalid JSON"}}`, http.StatusBadRequest)
			return
		}
		if request.Model == "" {
			request.Model = "claude-sonnet-4-5-20250929"
		}

		// Claude Code may end the request with a user message that is not the
		// tool_result itself, so any tool_result in the history marks a follow-up.
		followUp := false
		var shape []string
		for _, m := range request.Messages {
			var blocks []struct {
				Type string `json:"type"`
			}
			kinds := "text"
			if json.Unmarshal(m.Content, &blocks) == nil {
				kinds = ""
				for _, b := range blocks {
					kinds += b.Type + ","
					if b.Type == "tool_result" {
						followUp = true
					}
				}
			}
			shape = append(shape, m.Role+"["+kinds+"]")
		}
		hasRead := false
		for _, tool := range request.Tools {
			if tool.Name == "Read" {
				hasRead = true
			}
		}
		isToolTurn := !followUp && hasRead
		t.Logf("anthropic mock: messages=%v read_declared=%t tool_turn=%t", shape, hasRead, isToolTurn)

		if !request.Stream {
			w.Header().Set("Content-Type", "application/json")
			content := []map[string]interface{}{{"type": "text", "text": "claude-code-e2e-ok"}}
			stop := "end_turn"
			if isToolTurn {
				stop = "tool_use"
				content = nil
				for _, tu := range toolTurn {
					content = append(content, map[string]interface{}{"type": "tool_use", "id": tu.id, "name": tu.name, "input": tu.input})
				}
			}
			_ = json.NewEncoder(w).Encode(map[string]interface{}{
				"id": "msg_claude_code_e2e", "type": "message", "role": "assistant",
				"model": request.Model, "stop_reason": stop, "stop_sequence": nil,
				"content": content,
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

		type sseEvent struct{ name, data string }
		events := []sseEvent{
			{"message_start", fmt.Sprintf(`{"type":"message_start","message":{"id":"msg_claude_code_e2e","type":"message","role":"assistant","content":[],"model":%q,"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":10,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0}}}`, request.Model)},
		}
		if isToolTurn {
			for i, tu := range toolTurn {
				inputJSON, _ := json.Marshal(tu.input)
				partial, _ := json.Marshal(string(inputJSON))
				events = append(events,
					sseEvent{"content_block_start", fmt.Sprintf(`{"type":"content_block_start","index":%d,"content_block":{"type":"tool_use","id":%q,"name":%q,"input":{}}}`, i, tu.id, tu.name)},
					sseEvent{"content_block_delta", fmt.Sprintf(`{"type":"content_block_delta","index":%d,"delta":{"type":"input_json_delta","partial_json":%s}}`, i, partial)},
					sseEvent{"content_block_stop", fmt.Sprintf(`{"type":"content_block_stop","index":%d}`, i)},
				)
			}
			events = append(events, sseEvent{"message_delta", `{"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null},"usage":{"output_tokens":8}}`})
		} else {
			events = append(events,
				sseEvent{"content_block_start", `{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}`},
				sseEvent{"content_block_delta", `{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"claude-code-e2e-ok"}}`},
				sseEvent{"content_block_stop", `{"type":"content_block_stop","index":0}`},
				sseEvent{"message_delta", `{"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":8}}`},
			)
		}
		events = append(events, sseEvent{"message_stop", `{"type":"message_stop"}`})
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
