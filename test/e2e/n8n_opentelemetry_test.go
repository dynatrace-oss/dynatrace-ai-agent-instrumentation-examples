package e2e

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

const (
	n8nAppDir    = "n8n/opentelemetry"
	n8nBaseURL   = "http://127.0.0.1:5678"

	// n8nOpenAIWorkflowID must match the "id" in workflows/Webhook-AI-Workflow-OpenAI.json;
	// publish:workflow addresses the workflow by id.
	n8nOpenAIWebhookPath = "e2e-trigger-openai"
	n8nOpenAICredID      = "e2eOpenAICred01"
	n8nOpenAIWorkflowID  = "e2eAIWorkflow02"
)

// TestN8NOpenTelemetryOpenAI exercises the self-hosted n8n demo end to end
// using the OpenAI LangChain node (lmChatOpenAi).
//
// Unlike every other suite in this repo there is no application to run: n8n is a
// black-box container that emits its own native OTel traces, and the demo's value
// is the OTel Collector config that reshapes them for Dynatrace (root-span
// promotion, workflow.execute/<id> and node.execute/<type> renames). The test
// therefore starts the compose stack, seeds a webhook-triggered AI workflow plus
// its OpenAI credential through the n8n CLI, fires the webhook, and audits the
// resulting trace.
//
// Run isolation is by unique service.name, not scopedDQL: n8n builds its own
// OTel resource and does not read OTEL_RESOURCE_ATTRIBUTES, so test.run.id is
// absent, and its spans do not satisfy scopedDQL's timestamp fallback either, so
// applying it silently discards every span. See n8nServiceName.
func TestN8NOpenTelemetryOpenAI(t *testing.T) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		t.Skip("OPENAI_API_KEY not set — skipping OpenAI n8n variant")
	}

	service := n8nServiceName(t)

	startN8NStack(t)
	seedN8NWorkflowOpenAI(t, apiKey)
	triggerN8NWebhookPath(t, n8nOpenAIWebhookPath)

	agentTracingDQL := fmt.Sprintf(`fetch spans, from: now()-30m
| filter service.name == "%s"
| filter endsWith(span.name, ".generate") or endsWith(span.name, ".stream") or startsWith(span.name, "execute_tool") or isNotNull(gen_ai.operation.name) or isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`, service)

	auditN8NSpanMerged(t, "opentelemetry-openai",
		fmt.Sprintf(`fetch spans, from: now()-30m
| filter service.name == "%s"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`, service),
		[]string{agentTracingDQL}, false,
		"OpenAI variant — testing whether lmChatOpenAi emits gen_ai.request.model and other attributes that lmChatGoogleGemini does not.")

	t.Run("agent-tracing", func(t *testing.T) {
		auditN8NSpan(t, "opentelemetry-openai-agent", agentTracingDQL, true)
	})

	assertSpanExistsWithin(t, fmt.Sprintf(`fetch spans, from: now()-30m
| filter service.name == "%s"
| filter span.name == "workflow.execute/%s"
| limit 1`, service, n8nOpenAIWorkflowID), 5*time.Minute)
}

// n8nServiceName returns the service.name for this run and exports it as
// DT_SERVICE_NAME so the Makefile bakes it into .env, where both n8n (which
// stamps it on its spans) and the collector (which gates every transform/n8n
// statement on it) pick it up.
//
// It is unique per run because that is this suite's only workable isolation
// mechanism. scopedDQL cannot isolate n8n spans: n8n builds its own OTel
// resource, so test.run.id is absent, and its spans do not satisfy the
// timestamp fallback either, which silently filtered out every span. A unique
// service.name isolates concurrent runs exactly, and lets the queries below run
// unscoped.
func n8nServiceName(t *testing.T) string {
	t.Helper()
	name := fmt.Sprintf("n8n-e2e-%s", testRunID)
	t.Setenv("DT_SERVICE_NAME", name)
	return name
}

// auditN8NSpan is auditSpan without scopedDQL. It reuses the shared report
// pipeline so the output is identical to every other suite; only the run
// isolation differs, and the caller's DQL carries it via the unique
// service.name. optional skips instead of failing when no anchor is found.
func auditN8NSpan(t *testing.T, instrumentation string, dql string, optional bool, note ...string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), spanPollTimeout())
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil || len(records) == 0 {
		if optional {
			t.Skipf("no n8n/%s spans found: %v", instrumentation, err)
			return
		}
		t.Fatalf("poll DT spans: %v", err)
	}
	assertNotErrorSpan(t, records[0])

	spans := fetchTraceSpans(t, ctx, records[0])
	report := buildReport("n8n", instrumentation, GenericProfile, mergeSpans(spans))
	if len(note) > 0 {
		report.Note = note[0]
	}
	writeReport(t, report)
	logAuditResult(t, report, len(spans))
}

// auditN8NSpanMerged is like auditN8NSpan but also polls each DQL in extraDQLs
// best-effort, fetches every resulting trace's spans, and merges them all before
// evaluating GenericProfile. Use when gen_ai.* attributes live on spans in a
// separate trace (n8n's N8N_AGENTS_TRACING_ENABLED emits a new, unlinked trace
// per agent invocation) that would never be reached by expanding the workflow
// anchor's trace.id alone. Extra DQLs are silently skipped when they return no
// spans — they are always best-effort.
func auditN8NSpanMerged(t *testing.T, instrumentation, dql string, extraDQLs []string, optional bool, note ...string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), spanPollTimeout())
	defer cancel()

	records, err := dtClient.PollUntilSpans(ctx, dql, 15*time.Second)
	if err != nil || len(records) == 0 {
		if optional {
			t.Skipf("no n8n/%s spans found: %v", instrumentation, err)
			return
		}
		t.Fatalf("poll DT spans: %v", err)
	}
	assertNotErrorSpan(t, records[0])

	allSpans := fetchTraceSpans(t, ctx, records[0])

	for _, extra := range extraDQLs {
		extraRecords, extraErr := dtClient.PollUntilSpans(ctx, extra, 15*time.Second)
		if extraErr != nil || len(extraRecords) == 0 {
			t.Logf("n8n/%s: no spans for extra DQL (best-effort, skipping): %v", instrumentation, extraErr)
			continue
		}
		allSpans = append(allSpans, fetchTraceSpans(t, ctx, extraRecords[0])...)
	}

	report := buildReport("n8n", instrumentation, GenericProfile, mergeSpans(allSpans))
	if len(note) > 0 {
		report.Note = note[0]
	}
	writeReport(t, report)
	logAuditResult(t, report, len(allSpans))
}

// startN8NStack brings up postgres, n8n and the collector via make, and
// registers teardown. make run uses "docker compose up -d --wait", so it blocks
// until n8n reports healthy and then exits — there is no long-lived process to
// supervise, which is why this does not go through startApp/startCLIApp.
func startN8NStack(t *testing.T) {
	t.Helper()
	dir := filepath.Join(repoRoot(), n8nAppDir)

	t.Cleanup(func() {
		// n8n and the collector are both black boxes here: if no spans reach the
		// tenant there is nothing in the Go test output to distinguish "n8n never
		// exported" from "the collector could not reach Dynatrace". Dump both logs
		// before teardown so a failed run is diagnosable without a second run.
		if t.Failed() {
			// At detailed verbosity one span costs ~15 log lines plus its resource
			// block, so a small tail shows only the final batch and makes it easy to
			// conclude an attribute is absent when it was simply scrolled past.
			if err := runIn(dir, "docker", "compose", "logs", "--tail=2000", "n8n", "collector"); err != nil {
				t.Logf("warning: could not collect container logs: %v", err)
			}
			logN8NSpansInTenant(t)
		}
		if err := runIn(dir, "make", "-e", "stop"); err != nil {
			t.Logf("warning: make stop in %s: %v", n8nAppDir, err)
		}
	})

	// Remove any stale .env so the Makefile's file-based .env target always
	// regenerates it with the current DT_SERVICE_NAME for this run.
	_ = os.Remove(filepath.Join(dir, ".env"))

	if err := runIn(dir, "make", "-e", "install"); err != nil {
		t.Fatalf("make install in %s: %v", n8nAppDir, err)
	}
	if err := runIn(dir, "make", "-e", "run"); err != nil {
		t.Fatalf("make run in %s: %v", n8nAppDir, err)
	}
	waitN8NReady(t, 3*time.Minute)
}

// triggerN8NWebhookPath POSTs a topic to any workflow webhook by path. The
// workflow responds from its last node, so the call returns only once the AI
// Agent has finished and the spans have been handed to the collector.
func triggerN8NWebhookPath(t *testing.T, path string) {
	t.Helper()
	url := n8nBaseURL + "/webhook/" + path

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
// logN8NSpansInTenant asks the tenant what it actually stored for n8n, without
// the service.name filter or the run-isolation filter that the audit query
// applies. The collector's debug exporter can prove a span left the collector,
// but only the tenant can say whether it was stored and under which
// service.name, which is the one thing a failed audit cannot distinguish.
func logN8NSpansInTenant(t *testing.T) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	const dql = `fetch spans, from: now()-30m
| filter isNotNull(n8n.workflow.id)
| fields timestamp, span.name, service.name, n8n.workflow.id, test.run.id
| sort timestamp desc
| limit 5`

	records, err := dtClient.Execute(ctx, dql)
	if err != nil {
		t.Logf("diagnostic query failed: %v", err)
		return
	}
	if len(records) == 0 {
		t.Logf("diagnostic: tenant has no spans carrying n8n.workflow.id in the last 30m, " +
			"so the spans were accepted by the OTLP endpoint but not stored (check the " +
			"token's openpipeline:traces:ingest scope and that DT_ENDPOINT and " +
			"DT_APPS_ENDPOINT point at the same tenant)")
		return
	}
	// Rows here while the audit above found nothing means the audit's own filters
	// are wrong, not the ingest path: compare service.name against DT_SERVICE_NAME.
	t.Logf("diagnostic: expected service.name %q", os.Getenv("DT_SERVICE_NAME"))
	for _, r := range records {
		t.Logf("diagnostic: stored n8n span %v", r)
	}
}

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

// seedN8NWorkflowOpenAI imports the OpenAI credential and the OpenAI webhook
// workflow, then publishes it. Restarting n8n is required to register the new
// production webhook.
func seedN8NWorkflowOpenAI(t *testing.T, apiKey string) {
	t.Helper()
	dir := filepath.Join(repoRoot(), n8nAppDir)

	creds := []map[string]interface{}{{
		"id":   n8nOpenAICredID,
		"name": "E2E OpenAI",
		"type": "openAiApi",
		"data": map[string]string{
			"apiKey": apiKey,
		},
	}}
	credPath := filepath.Join(t.TempDir(), "credentials.json")
	writeJSON(t, credPath, creds)

	src := filepath.Join(repoRoot(), n8nAppDir, "workflows", "Webhook-AI-Workflow-OpenAI.json")
	raw, err := os.ReadFile(src)
	if err != nil {
		t.Fatalf("read OpenAI workflow %s: %v", src, err)
	}
	var wf map[string]interface{}
	if err := json.Unmarshal(raw, &wf); err != nil {
		t.Fatalf("parse OpenAI workflow %s: %v", src, err)
	}
	if model := os.Getenv("MODEL"); model != "" {
		nodes, _ := wf["nodes"].([]interface{})
		for _, n := range nodes {
			node, ok := n.(map[string]interface{})
			if !ok || node["type"] != "@n8n/n8n-nodes-langchain.lmChatOpenAi" {
				continue
			}
			if params, ok := node["parameters"].(map[string]interface{}); ok {
				params["model"] = model
			}
		}
	}
	wfPath := filepath.Join(t.TempDir(), "workflow.json")
	writeJSON(t, wfPath, wf)

	copyIntoN8N(t, dir, credPath, "/tmp/credentials-openai.json")
	copyIntoN8N(t, dir, wfPath, "/tmp/workflow-openai.json")

	execInN8N(t, dir, "n8n", "import:credentials", "--input=/tmp/credentials-openai.json")
	execInN8N(t, dir, "n8n", "import:workflow", "--input=/tmp/workflow-openai.json")
	execInN8N(t, dir, "n8n", "publish:workflow", "--id="+n8nOpenAIWorkflowID)

	if err := runIn(dir, "docker", "compose", "restart", "n8n"); err != nil {
		t.Fatalf("restart n8n for OpenAI workflow: %v", err)
	}
	waitN8NReady(t, 3*time.Minute)
}
