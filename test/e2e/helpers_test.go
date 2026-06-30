package e2e

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"
	"time"

	"github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples/test/e2e/internal/process"
)

func repoRoot() string {
	_, f, _, _ := runtime.Caller(0)
	// helpers_test.go lives at test/e2e/ — go up two directories.
	return filepath.Join(filepath.Dir(f), "..", "..")
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

// startApp runs make install then starts make run in <repoRoot>/<appDir>.
// Registers cleanup to stop the app and, for apps with a collector, make stop.
func startApp(t *testing.T, appDir string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)

	install := exec.Command("make", "install")
	install.Dir = dir
	// install only needs PATH and HOME — no credentials required for package installation
	install.Env = []string{
		"PATH=" + os.Getenv("PATH"),
		"HOME=" + os.Getenv("HOME"),
	}
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		t.Fatalf("make install in %s: %v", appDir, err)
	}

	app, err := process.Start(dir)
	if err != nil {
		t.Fatalf("start app %s: %v", appDir, err)
	}
	t.Cleanup(func() {
		if err := app.Stop(); err != nil {
			t.Logf("warning: stop app %s: %v", appDir, err)
		}
		// noop for apps without a stop target (e.g. plain oneagent apps)
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})
}

// startCLIApp runs make install then starts make run in <repoRoot>/<appDir>
// without waiting for an HTTP readiness endpoint. The app emits telemetry
// autonomously; use assertGenAISpan to wait for spans.
func startCLIApp(t *testing.T, appDir string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)

	install := exec.Command("make", "install")
	install.Dir = dir
	install.Env = []string{
		"PATH=" + os.Getenv("PATH"),
		"HOME=" + os.Getenv("HOME"),
	}
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		t.Fatalf("make install in %s: %v", appDir, err)
	}

	app, err := process.StartCLI(dir)
	if err != nil {
		t.Fatalf("start cli app %s: %v", appDir, err)
	}
	t.Cleanup(func() {
		if err := app.Stop(); err != nil {
			t.Logf("warning: stop cli app %s: %v", appDir, err)
		}
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})
}

// startCLIAppWithTarget runs make install then starts make <target> in <repoRoot>/<appDir>.
// Use when a non-default make target is needed (e.g. "run-openpipeline").
func startCLIAppWithTarget(t *testing.T, appDir, target string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), appDir)

	install := exec.Command("make", "install")
	install.Dir = dir
	install.Env = []string{
		"PATH=" + os.Getenv("PATH"),
		"HOME=" + os.Getenv("HOME"),
	}
	install.Stdout = os.Stdout
	install.Stderr = os.Stderr
	if err := install.Run(); err != nil {
		t.Fatalf("make install in %s: %v", appDir, err)
	}

	app, err := process.StartCLIWithTarget(dir, target)
	if err != nil {
		t.Fatalf("start cli app %s (%s): %v", appDir, target, err)
	}
	t.Cleanup(func() {
		if err := app.Stop(); err != nil {
			t.Logf("warning: stop cli app %s: %v", appDir, err)
		}
		if err := exec.Command("make", "-C", dir, "stop").Run(); err != nil {
			t.Logf("warning: make stop in %s: %v", appDir, err)
		}
	})
}

// assertSpanExists polls DT until at least one span matching dql is found
// (3-minute timeout). Use this when the relevant attribute cannot be asserted
// (e.g. instrumentation libraries that don't emit gen_ai.system).
func assertSpanExists(t *testing.T, dql string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	_, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
}

// assertSpanWithAttrs polls DT until a span matching dql is found (3-minute
// timeout), then asserts that every attribute in required is non-null, and that
// at least one attribute in each anyOf group is non-null.
func assertSpanWithAttrs(t *testing.T, dql string, required []string, anyOf [][]string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
	if len(records) == 0 {
		t.Fatal("no spans returned from DT")
	}

	span := records[0]
	for _, attr := range required {
		v, ok := span[attr]
		if !ok || v == nil || v == "" {
			t.Errorf("span missing required attribute %q", attr)
		}
	}
	for _, group := range anyOf {
		found := false
		for _, attr := range group {
			if v, ok := span[attr]; ok && v != nil && v != "" {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("span missing at least one of %v", group)
		}
	}
}

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
}

// assertGenAISpan polls DT until a span matching dql is found (3-minute
// timeout), then asserts gen_ai.system equals wantSystem.
func assertGenAISpan(t *testing.T, dql, wantSystem string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil {
		t.Fatalf("poll DT spans: %v", err)
	}
	if len(records) == 0 {
		t.Fatal("no spans returned from DT")
	}

	span := records[0]
	system, ok := span["gen_ai.provider.name"]
	if !ok {
		system, ok = span["gen_ai.system"]
	}
	if !ok {
		t.Fatal("span missing gen_ai.provider.name and gen_ai.system")
	}
	if system != wantSystem {
		t.Errorf("gen_ai.provider.name/gen_ai.system = %q, want %q", system, wantSystem)
	}
}
