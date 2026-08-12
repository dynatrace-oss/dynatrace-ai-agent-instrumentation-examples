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
// Run isolation is by unique service.name, not scopedDQL: n8n builds its own
// OTel resource and does not read OTEL_RESOURCE_ATTRIBUTES, so test.run.id is
// absent, and its spans do not satisfy scopedDQL's timestamp fallback either, so
// applying it silently discards every span. See n8nServiceName.
func TestN8NOpenTelemetry(t *testing.T) {
	apiKey := os.Getenv("GOOGLE_API_KEY")
	if apiKey == "" {
		t.Skip("GOOGLE_API_KEY not set — n8n suite needs a real Gemini key for the AI Agent node")
	}

	service := n8nServiceName(t)

	startN8NStack(t)
	seedN8NWorkflow(t, apiKey)
	triggerN8NWebhook(t)

	// n8n's agent tracing (N8N_AGENTS_TRACING_ENABLED, n8n >= 2.33.0) emits
	// gen_ai.* spans in a trace of their own, not connected to the workflow
	// execution trace. Build the DQL once and reuse it in both the merged main
	// audit and the dedicated agent-tracing sub-test.
	agentTracingDQL := fmt.Sprintf(`fetch spans, from: now()-30m
| filter service.name == "%s"
| filter endsWith(span.name, ".generate") or endsWith(span.name, ".stream") or startsWith(span.name, "execute_tool") or isNotNull(gen_ai.operation.name) or isNotNull(gen_ai.request.model)
| sort timestamp desc
| limit 1`, service)

	// Anchor on service.name alone rather than on a gen_ai.* attribute or a span
	// name: the LLM attributes live on the agent-tracing spans, which arrive in a
	// separate trace. auditN8NSpanMerged fetches the workflow trace first (keeping
	// the anchor broad so a failure here means "no n8n spans reached the tenant"),
	// then best-effort fetches the agent-tracing trace and merges both before
	// evaluating the profile — so gen_ai.* attributes are visible even though they
	// live in a different trace from workflow.execute/node.execute spans.
	auditN8NSpanMerged(t, "opentelemetry",
		fmt.Sprintf(`fetch spans, from: now()-30m
| filter service.name == "%s"
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`, service),
		[]string{agentTracingDQL}, false,
		"n8n emits gen_ai.* attributes on agent-tracing spans (N8N_AGENTS_TRACING_ENABLED) in a separate trace; merged here for a complete profile picture.")

	// The agent-tracing sub-test produces a dedicated "opentelemetry-agent"
	// report anchored solely on the gen_ai spans. Optional: a version or node
	// typeVersion whose agent runtime is not instrumented emits none of this, and
	// that is a finding to report rather than a reason to fail the suite.
	t.Run("agent-tracing", func(t *testing.T) {
		auditN8NSpan(t, "opentelemetry-agent", agentTracingDQL, true)
	})

	// The collector's transform/n8n statements rename the workflow root span to
	// workflow.execute/<workflow.id>. Asserted separately, and after the audit,
	// so a rename regression does not cost us the attribute report.
	assertSpanExistsWithin(t, fmt.Sprintf(`fetch spans, from: now()-30m
| filter service.name == "%s"
| filter span.name == "workflow.execute/%s"
| limit 1`, service, n8nWorkflowID), 5*time.Minute)
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
