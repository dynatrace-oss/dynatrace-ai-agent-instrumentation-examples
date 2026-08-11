package e2e

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const (
	n8nAppDir      = "n8n/opentelemetry"
	n8nBaseURL     = "http://127.0.0.1:5678"
	n8nWebhookPath = "e2e-trigger"
	n8nCredID      = "e2eGeminiCred01"
	// n8nWorkflowID must match the "id" in workflows/Webhook-AI-Workflow.json;
	// publish:workflow addresses the workflow by id.
	n8nWorkflowID = "e2eAIWorkflow01"
)

// TestN8NOpenTelemetry exercises the self-hosted n8n demo end to end.
//
// Unlike every other suite in this repo there is no application to run: n8n is a
// black-box container that emits its own native OTel traces, and the demo's value
// is the OTel Collector config that reshapes them for Dynatrace (root-span
// promotion, workflow.execute/<id> and node.execute/<type> renames). The test
// therefore starts the compose stack, seeds a webhook-triggered AI workflow plus
// its Gemini credential through the n8n CLI, fires the webhook, and audits the
// resulting trace.
//
// Run isolation is timestamp-based, not test.run.id-based: n8n builds its own
// resource and does not read OTEL_RESOURCE_ATTRIBUTES, exactly like the OneAgent
// suites. scopedDQL's isNull(test.run.id) branch covers this.
func TestN8NOpenTelemetry(t *testing.T) {
	apiKey := os.Getenv("GOOGLE_API_KEY")
	if apiKey == "" {
		t.Skip("GOOGLE_API_KEY not set — n8n suite needs a real Gemini key for the AI Agent node")
	}

	startN8NStack(t)
	seedN8NWorkflow(t, apiKey)
	triggerN8NWebhook(t)

	// Anchor on the workflow root span rather than on a gen_ai.* attribute: the
	// LLM attributes live on the agent's child spans, and auditSpan expands the
	// anchor to every span in its trace before evaluating the profile. Anchoring
	// on the root also proves the collector's transform/n8n rename fired.
	auditSpan(t, "n8n", "opentelemetry", GenericProfile,
		fmt.Sprintf(`fetch spans, from: now()-10m
| filter service.name == "%s"
| filter startsWith(span.name, "workflow.execute")
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`, n8nServiceName()),
		"n8n emits native OTel traces; gen_ai.* attributes come from the AI Agent node's child spans.")
}

// n8nServiceName is the service.name n8n stamps on its spans. It must match
// DT_SERVICE_NAME in the compose env, because the collector's transform/n8n
// statements are all gated on that value.
func n8nServiceName() string {
	return envOr("DT_SERVICE_NAME", "n8n")
}

// startN8NStack brings up postgres, n8n and the collector via make, and
// registers teardown. make run uses "docker compose up -d --wait", so it blocks
// until n8n reports healthy and then exits — there is no long-lived process to
// supervise, which is why this does not go through startApp/startCLIApp.
func startN8NStack(t *testing.T) {
	t.Helper()
	dir := filepath.Join(repoRoot(), n8nAppDir)

	t.Cleanup(func() {
		if err := runIn(dir, "make", "-e", "stop"); err != nil {
			t.Logf("warning: make stop in %s: %v", n8nAppDir, err)
		}
	})

	if err := runIn(dir, "make", "-e", "install"); err != nil {
		t.Fatalf("make install in %s: %v", n8nAppDir, err)
	}
	if err := runIn(dir, "make", "-e", "run"); err != nil {
		t.Fatalf("make run in %s: %v", n8nAppDir, err)
	}
	waitN8NReady(t, 3*time.Minute)
}

// seedN8NWorkflow imports the Gemini credential and the webhook workflow through
// the n8n CLI, then restarts n8n. The restart is required: workflows imported via
// the CLI are written straight to the database, and a running instance only
// registers production webhooks for active workflows at startup.
func seedN8NWorkflow(t *testing.T, apiKey string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), n8nAppDir)

	creds := []map[string]interface{}{{
		"id":   n8nCredID,
		"name": "E2E Gemini",
		"type": "googlePalmApi",
		"data": map[string]string{
			"host":   "https://generativelanguage.googleapis.com",
			"apiKey": apiKey,
		},
	}}
	credPath := filepath.Join(t.TempDir(), "credentials.json")
	writeJSON(t, credPath, creds)

	wfPath := filepath.Join(t.TempDir(), "workflow.json")
	writeJSON(t, wfPath, n8nWorkflowWithModel(t))

	copyIntoN8N(t, dir, credPath, "/tmp/credentials.json")
	copyIntoN8N(t, dir, wfPath, "/tmp/workflow.json")

	execInN8N(t, dir, "n8n", "import:credentials", "--input=/tmp/credentials.json")
	execInN8N(t, dir, "n8n", "import:workflow", "--input=/tmp/workflow.json")
	// publish:workflow replaces "update:workflow --all --active=true", which is
	// deprecated and silently publishes nothing. The workflow's "active": true
	// flag in the JSON is not enough on its own either.
	execInN8N(t, dir, "n8n", "publish:workflow", "--id="+n8nWorkflowID)

	if err := runIn(dir, "docker", "compose", "restart", "n8n"); err != nil {
		t.Fatalf("restart n8n: %v", err)
	}
	waitN8NReady(t, 3*time.Minute)
}

// n8nWorkflowWithModel loads the committed webhook workflow and overrides the
// Gemini model with MODEL when the matrix supplies one, so the model under test
// is pinned in one place (the CI matrix) rather than in the demo asset.
func n8nWorkflowWithModel(t *testing.T) map[string]interface{} {
	t.Helper()
	src := filepath.Join(repoRoot(), n8nAppDir, "workflows", "Webhook-AI-Workflow.json")
	raw, err := os.ReadFile(src)
	if err != nil {
		t.Fatalf("read workflow %s: %v", src, err)
	}
	var wf map[string]interface{}
	if err := json.Unmarshal(raw, &wf); err != nil {
		t.Fatalf("parse workflow %s: %v", src, err)
	}

	model := os.Getenv("MODEL")
	if model == "" {
		return wf
	}
	if !strings.HasPrefix(model, "models/") {
		model = "models/" + model
	}
	nodes, _ := wf["nodes"].([]interface{})
	for _, n := range nodes {
		node, ok := n.(map[string]interface{})
		if !ok || node["type"] != "@n8n/n8n-nodes-langchain.lmChatGoogleGemini" {
			continue
		}
		params, ok := node["parameters"].(map[string]interface{})
		if !ok {
			continue
		}
		params["modelName"] = model
	}
	return wf
}

// triggerN8NWebhook POSTs a topic to the workflow's production webhook. The
// workflow responds from its last node, so the call returns only once the AI
// Agent has finished and the spans have been handed to the collector.
func triggerN8NWebhook(t *testing.T) {
	t.Helper()
	url := n8nBaseURL + "/webhook/" + n8nWebhookPath

	body, _ := json.Marshal(map[string]string{"topic": "observability"})
	client := &http.Client{Timeout: 2 * time.Minute}

	// The webhook can 404 for a short window after restart while n8n finishes
	// registering active workflows; retry rather than fail on the first miss.
	deadline := time.Now().Add(2 * time.Minute)
	for {
		resp, err := client.Post(url, "application/json", bytes.NewReader(body))
		if err == nil {
			b, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode < 300 {
				return
			}
			if time.Now().After(deadline) {
				t.Fatalf("POST %s returned %d: %s", url, resp.StatusCode, b)
			}
		} else if time.Now().After(deadline) {
			t.Fatalf("POST %s: %v", url, err)
		}
		time.Sleep(5 * time.Second)
	}
}

// waitN8NReady polls n8n's /healthz until it reports ready.
func waitN8NReady(t *testing.T, timeout time.Duration) {
	t.Helper()
	client := &http.Client{Timeout: 5 * time.Second}
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		resp, err := client.Get(n8nBaseURL + "/healthz")
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return
			}
		}
		time.Sleep(2 * time.Second)
	}
	t.Fatalf("n8n not ready on /healthz after %v", timeout)
}

// copyIntoN8N copies a file into the n8n container and hands it to the node
// user. docker compose cp preserves the source mode and uid, and these files are
// written 0600 by the runner's uid, so without the chown the n8n CLI (running as
// node) fails to read them with EACCES.
func copyIntoN8N(t *testing.T, dir, src, dest string) {
	t.Helper()
	if err := runIn(dir, "docker", "compose", "cp", src, "n8n:"+dest); err != nil {
		t.Fatalf("copy %s into n8n container: %v", src, err)
	}
	if err := runIn(dir, "docker", "compose", "exec", "-T", "-u", "root", "n8n",
		"chown", "node:node", dest); err != nil {
		t.Fatalf("chown %s in n8n container: %v", dest, err)
	}
}

func execInN8N(t *testing.T, dir string, args ...string) {
	t.Helper()
	full := append([]string{"compose", "exec", "-T", "n8n"}, args...)
	if err := runIn(dir, "docker", full...); err != nil {
		t.Fatalf("docker compose exec n8n %v: %v", args, err)
	}
}

// writeJSON marshals v into path. Credential files written this way contain a
// live API key, so they only ever land in the per-test TempDir, which Go removes
// on test exit.
func writeJSON(t *testing.T, path string, v interface{}) {
	t.Helper()
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		t.Fatalf("marshal %s: %v", path, err)
	}
	if err := os.WriteFile(path, b, 0o600); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func runIn(dir, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	cmd.Env = os.Environ()
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}
