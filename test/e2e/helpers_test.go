package e2e

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
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
	system, ok := span["gen_ai.system"]
	if !ok {
		t.Fatal("span missing gen_ai.system")
	}
	if system != wantSystem {
		t.Errorf("gen_ai.system = %q, want %q", system, wantSystem)
	}
}
