package e2e

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

// runMakeTarget runs a Makefile target in the given app directory (e.g. "request"
// or "request-secret"). It is used by tests that drive their app via make rather
// than a direct HTTP call so that topic strings and curl flags stay in one place.
func runMakeTarget(t *testing.T, appDir, target string) {
	t.Helper()
	cmd := exec.Command("make", "-C", filepath.Join(repoRoot(), appDir), target)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		t.Fatalf("make %s in %s: %v", target, appDir, err)
	}
}

// triggerIngest POSTs to /ingest on localhost:8000. The dt-evals-fixtures app
// replays every deterministic fixture as GenAI spans in a single call — no body,
// no real LLM. Returns once all fixtures have been shipped to the tenant.
func triggerIngest(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/ingest"

	resp, err := http.Post(url, "application/json", nil)
	if err != nil {
		t.Fatalf("POST /ingest: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /ingest returned %d: %s", resp.StatusCode, b)
	}
}

type haiku struct {
	Topic string `json:"topic,omitempty"`
	Haiku string `json:"haiku,omitempty"`
}

// triggerHaiku POSTs to /haiku on localhost:8000. withBody sends a JSON topic
// payload; otherwise the request has no body.
func triggerHaiku(t *testing.T, withBody bool) {
	t.Helper()
	const url = "http://127.0.0.1:8000/haiku"

	var body io.Reader
	if withBody {
		b, _ := json.Marshal(haiku{Topic: "e2e test"})
		body = bytes.NewReader(b)
	}

	req, err := http.NewRequest(http.MethodPost, url, body)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	if withBody {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /haiku: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /haiku returned %d: %s", resp.StatusCode, b)
	}
}

// triggerHaikuGuardrail POSTs a football-topic request to /haiku on
// localhost:8000 to trip the demo's Bedrock guardrail (a topic-denial policy
// on "football"). No-op when BEDROCK_GUARDRAIL_ID is unset, matching the
// app-side skip behavior — nothing would fire anyway.
func triggerHaikuGuardrail(t *testing.T) {
	t.Helper()
	if os.Getenv("BEDROCK_GUARDRAIL_ID") == "" {
		return
	}
	const url = "http://127.0.0.1:8000/haiku"

	b, _ := json.Marshal(haiku{Topic: "football strategies for the World Cup"})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /haiku (guardrail trigger): %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		rb, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /haiku (guardrail trigger) returned %d: %s", resp.StatusCode, rb)
	}
}

// triggerAgent POSTs a task to /agent on localhost:8000.
func triggerAgent(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/agent"

	b, _ := json.Marshal(map[string]string{
		"task": "Book 'Agent fun' for tomorrow 3pm in NYC. This meeting will discuss all the fun things that an agent can do",
	})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /agent: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /agent returned %d: %s", resp.StatusCode, body)
	}
}

// triggerAgentCoreHarness POSTs a topic to /invoke on localhost:8000
// (aws-bedrock-agentcore/opentelemetry). MOCK_AGENTCORE=true in that app's
// environment replays a synthetic InvokeHarness stream instead of calling AWS,
// so this trigger works without real harness credentials.
func triggerAgentCoreHarness(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/invoke"

	b, _ := json.Marshal(map[string]string{"topic": "plan a weekend in Seattle"})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /invoke: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /invoke returned %d: %s", resp.StatusCode, body)
	}
}

// triggerAgentGuardrail POSTs a football-topic task to /agent on
// localhost:8000 to trip the demo's Bedrock guardrail (a topic-denial policy
// on "football"). No-op when BEDROCK_GUARDRAIL_ID is unset.
func triggerAgentGuardrail(t *testing.T) {
	t.Helper()
	if os.Getenv("BEDROCK_GUARDRAIL_ID") == "" {
		return
	}
	const url = "http://127.0.0.1:8000/agent"

	b, _ := json.Marshal(map[string]string{
		"task": "What are the best football strategies for the World Cup?",
	})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /agent (guardrail trigger): %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /agent (guardrail trigger) returned %d: %s", resp.StatusCode, body)
	}
}

// triggerResearch POSTs to /research on localhost:8000 with a paper topic.
func triggerResearch(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/research"

	b, _ := json.Marshal(map[string]string{"topic": "Attention is All You Need"})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /research: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		rb, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /research returned %d: %s", resp.StatusCode, rb)
	}
}

// triggerRUMMusicAgent POSTs to /api/ask with an explicit conversationID.
// Call it repeatedly with the same ID to simulate an agentic session that
// spans multiple traces — the browser does the same via sessionStorage.
func triggerRUMMusicAgent(t *testing.T, conversationID string) {
	t.Helper()
	const url = "http://127.0.0.1:8000/api/ask"

	b, _ := json.Marshal(map[string]string{
		"question":        "Tell me about the history of jazz music",
		"conversation_id": conversationID,
	})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /api/ask: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /api/ask returned %d: %s", resp.StatusCode, b)
	}
}

// triggerMusicAgent POSTs a question to /api/ask on localhost:8000.
func triggerMusicAgent(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/api/ask"

	b, _ := json.Marshal(map[string]string{"question": "Tell me the what is the shortest music known"})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /api/ask: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /api/ask returned %d: %s", resp.StatusCode, b)
	}
}

// triggerMCPAgent POSTs a weather question to /invoke on localhost:8000.
func triggerMCPAgent(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/invoke"

	b, _ := json.Marshal(map[string]string{"message": "What is the weather?"})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /invoke: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /invoke returned %d: %s", resp.StatusCode, b)
	}
}

// triggerCSAgent POSTs an airline question to /chat on localhost:8000.
func triggerCSAgent(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/chat"

	b, _ := json.Marshal(map[string]string{"message": "What is the baggage allowance for economy class?"})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /chat: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /chat returned %d: %s", resp.StatusCode, b)
	}
}

// triggerLiteLLMChat POSTs a chat completion request to /chat/completions on localhost:8000.
// When OPENAI_API_VERSION is set the environment is Azure; the model is prefixed with
// "azure/" so LiteLLM routes to the Azure deployment instead of api.openai.com.
func triggerLiteLLMChat(t *testing.T) {
	t.Helper()
	const url = "http://127.0.0.1:8000/chat/completions"

	model := "gpt-5.4-mini"
	if deployment := os.Getenv("MODEL"); deployment != "" && os.Getenv("OPENAI_API_VERSION") != "" {
		model = "azure/" + deployment
	}

	b, _ := json.Marshal(map[string]interface{}{
		"model": model,
		"messages": []map[string]string{
			{"role": "user", "content": "Write a haiku about observability"},
		},
	})
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST /chat/completions: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		t.Fatalf("POST /chat/completions returned %d: %s", resp.StatusCode, b)
	}
}
