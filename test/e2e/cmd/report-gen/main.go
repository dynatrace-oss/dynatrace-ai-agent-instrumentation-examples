// report-gen reads *.json SpanReport files and renders a self-contained HTML dashboard.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"html/template"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// AttributeResult mirrors the type in fixture_audit_test.go (standalone binary, no import).
type AttributeResult struct {
	RuleID       string `json:"rule_id"`
	Attribute    string `json:"attribute"`
	Status       string `json:"status"`
	FallbackUsed string `json:"fallback_used,omitempty"`
}

// SpanReport mirrors the type in fixture_audit_test.go.
type SpanReport struct {
	SDK             string            `json:"sdk"`
	Instrumentation string            `json:"instrumentation"`
	Profile         string            `json:"profile"`
	Verdict         string            `json:"verdict"`
	Note            string            `json:"note,omitempty"`
	Required        []AttributeResult `json:"required"`
	Optional        []AttributeResult `json:"optional"`
	GeneratedAt     string            `json:"generated_at"`
}

// RunSummary is one entry in history.json.
type RunSummary struct {
	Date   string `json:"date"`
	RunURL string `json:"run_url"`
	Full   int    `json:"full"`
	Pass   int    `json:"pass"`
	Fail   int    `json:"fail"`
	Total  int    `json:"total"`
}

// viewReport adds computed display fields to SpanReport.
type viewReport struct {
	SpanReport
	Index      int
	ReqPass    int
	ReqTotal   int
	OptPresent int
	OptTotal   int
}

type pageData struct {
	RunDate string
	RunURL  string
	Reports []viewReport
	History []RunSummary // most-recent first
	Full    int
	Pass    int
	Fail    int
	Total   int
}

func main() {
	inputDir := flag.String("input", ".", "directory containing *.json SpanReport files")
	outputFile := flag.String("output", "index.html", "output HTML path")
	runURL := flag.String("run-url", "", "URL of the CI run (linked in header)")
	historyFile := flag.String("history-file", "", "path to history.json to read (optional)")
	historyOutput := flag.String("history-output", "", "path to write updated history.json (optional)")
	flag.Parse()

	reports, err := loadReports(*inputDir)
	if err != nil {
		fatalf("load reports: %v", err)
	}
	sort.Slice(reports, func(i, j int) bool {
		return reports[i].SDK+"/"+reports[i].Instrumentation <
			reports[j].SDK+"/"+reports[j].Instrumentation
	})

	history := loadHistory(*historyFile)
	data := buildPageData(reports, history, *runURL)

	if err := renderHTML(data, *outputFile); err != nil {
		fatalf("render HTML: %v", err)
	}
	fmt.Printf("wrote %s (%d reports)\n", *outputFile, len(reports))

	if *historyOutput != "" {
		updated := appendHistory(history, data)
		if err := writeHistory(*historyOutput, updated); err != nil {
			fatalf("write history: %v", err)
		}
		fmt.Printf("wrote %s (%d entries)\n", *historyOutput, len(updated))
	}
}

func loadReports(dir string) ([]SpanReport, error) {
	entries, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return nil, err
	}
	var reports []SpanReport
	for _, path := range entries {
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", path, err)
		}
		var r SpanReport
		if err := json.Unmarshal(data, &r); err != nil {
			return nil, fmt.Errorf("parse %s: %w", path, err)
		}
		reports = append(reports, r)
	}
	return reports, nil
}

func loadHistory(path string) []RunSummary {
	if path == "" {
		return nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var h []RunSummary
	if err := json.Unmarshal(data, &h); err != nil {
		return nil
	}
	return h
}

func buildPageData(reports []SpanReport, history []RunSummary, runURL string) pageData {
	views := make([]viewReport, len(reports))
	var full, pass, fail int

	for i, r := range reports {
		v := viewReport{SpanReport: r, Index: i}
		for _, a := range r.Required {
			v.ReqTotal++
			if a.Status == "pass" || a.Status == "pass_via_fallback" {
				v.ReqPass++
			}
		}
		for _, a := range r.Optional {
			v.OptTotal++
			if a.Status == "present" || a.Status == "present_via_fallback" {
				v.OptPresent++
			}
		}
		switch r.Verdict {
		case "FULL":
			full++
		case "PASS":
			pass++
		default:
			fail++
		}
		views[i] = v
	}

	// Show history most-recent first.
	reversed := make([]RunSummary, len(history))
	for i, v := range history {
		reversed[len(history)-1-i] = v
	}

	return pageData{
		RunDate: time.Now().UTC().Format("2006-01-02 15:04 UTC"),
		RunURL:  runURL,
		Reports: views,
		History: reversed,
		Full:    full,
		Pass:    pass,
		Fail:    fail,
		Total:   len(reports),
	}
}

func appendHistory(existing []RunSummary, data pageData) []RunSummary {
	entry := RunSummary{
		Date:   time.Now().UTC().Format("2006-01-02"),
		RunURL: data.RunURL,
		Full:   data.Full,
		Pass:   data.Pass,
		Fail:   data.Fail,
		Total:  data.Total,
	}
	updated := append(existing, entry)
	if len(updated) > 30 {
		updated = updated[len(updated)-30:]
	}
	return updated
}

func writeHistory(path string, history []RunSummary) error {
	data, err := json.MarshalIndent(history, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

func renderHTML(data pageData, outputFile string) error {
	funcMap := template.FuncMap{
		"lower": strings.ToLower,
		"dateOf": func(s string) string {
			if len(s) >= 10 {
				return s[:10]
			}
			return s
		},
		"statusClass": func(s string) string {
			switch s {
			case "pass", "present":
				return "pass"
			case "pass_via_fallback", "present_via_fallback":
				return "fallback"
			case "fail":
				return "fail"
			default:
				return "absent"
			}
		},
		"statusIcon": func(s string) string {
			switch s {
			case "pass", "present":
				return "✅"
			case "pass_via_fallback", "present_via_fallback":
				return "🔄"
			case "fail":
				return "❌"
			default:
				return "⚪"
			}
		},
	}

	tmpl, err := template.New("dashboard").Funcs(funcMap).Parse(dashboardHTML)
	if err != nil {
		return fmt.Errorf("parse template: %w", err)
	}

	f, err := os.Create(outputFile)
	if err != nil {
		return err
	}
	defer f.Close()

	return tmpl.Execute(f, data)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "report-gen: "+format+"\n", args...)
	os.Exit(1)
}

const dashboardHTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Observability — Span Audit Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 14px;
  line-height: 1.5;
}
a { color: #60a5fa; text-decoration: none; }
a:hover { text-decoration: underline; }

header {
  padding: 24px 32px 20px;
  border-bottom: 1px solid #334155;
}
h1 { font-size: 20px; font-weight: 600; margin-bottom: 6px; }
.meta { color: #94a3b8; font-size: 13px; margin-bottom: 16px; }
.stats { display: flex; gap: 10px; flex-wrap: wrap; }
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 12px; border-radius: 9999px;
  font-size: 13px; font-weight: 600;
}
.badge.full    { background: rgba(139,92,246,0.12);  color: #c084fc; border: 1px solid rgba(139,92,246,0.25); }
.badge.pass    { background: rgba(34,197,94,0.12);  color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
.badge.fail    { background: rgba(239,68,68,0.12);  color: #f87171; border: 1px solid rgba(239,68,68,0.25); }
.badge.total   { background: rgba(148,163,184,0.08); color: #94a3b8; border: 1px solid rgba(148,163,184,0.15); }

main { padding: 24px 32px; max-width: 1400px; }
h2 { font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #94a3b8;
     text-transform: uppercase; letter-spacing: 0.06em; }

.table-wrap { overflow-x: auto; margin-bottom: 36px; border-radius: 8px; border: 1px solid #334155; }
table { border-collapse: collapse; width: 100%; }

thead th {
  background: #1e293b;
  padding: 9px 14px;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  white-space: nowrap;
  border-bottom: 1px solid #334155;
}

tbody tr.summary-row {
  cursor: pointer;
  border-bottom: 1px solid #1a2438;
  transition: background 0.1s;
}
tbody tr.summary-row:hover  { background: #1a2438; }
tbody tr.summary-row.expanded { background: #1a2438; }

tbody td { padding: 10px 14px; vertical-align: middle; }

.toggle { color: #475569; font-size: 10px; display: inline-block; transition: transform 0.15s; }
.expanded .toggle { transform: rotate(90deg); }

.verdict-badge {
  display: inline-block;
  padding: 2px 9px; border-radius: 9999px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
}
.verdict-full    { background: rgba(139,92,246,0.12);  color: #c084fc; }
.verdict-pass    { background: rgba(34,197,94,0.12);  color: #4ade80; }
.verdict-fail    { background: rgba(239,68,68,0.12);  color: #f87171; }

.sdk    { font-weight: 600; }
.instr  { color: #64748b; }
.count  { font-size: 13px; font-variant-numeric: tabular-nums; }
.ok     { color: #4ade80; }
.warn   { color: #fbbf24; }
.err    { color: #f87171; }
.note   { color: #c084fc; font-size: 12px; font-style: italic; }
.gen-at { color: #475569; font-size: 12px; }

tr.detail-row td { padding: 0; background: #080f1e; border-bottom: 2px solid #334155; }
.detail-inner { padding: 16px 20px; }
.detail-grid  {
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
}
@media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }

.detail-section h3 {
  font-size: 11px; font-weight: 600; color: #475569;
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;
}
.attr-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.attr-table th {
  text-align: left; padding: 4px 8px;
  color: #475569; font-weight: 500;
  border-bottom: 1px solid #1e293b;
}
.attr-table td { padding: 4px 8px; border-bottom: 1px solid #0f172a; }
code { font-family: 'SF Mono', Consolas, 'Courier New', monospace; color: #7dd3fc; font-size: 11px; }

.s-pass     { color: #4ade80; }
.s-fallback { color: #a78bfa; }
.s-fail     { color: #f87171; }
.s-absent   { color: #334155; }

.empty-state {
  padding: 48px; text-align: center; color: #475569;
  font-size: 15px;
}

.history-table td, .history-table th { padding: 8px 14px; }

footer {
  padding: 20px 32px;
  border-top: 1px solid #1e293b;
  color: #334155;
  font-size: 12px;
}
</style>
</head>
<body>

<header>
  <h1>AI Observability &mdash; Span Audit Dashboard</h1>
  <p class="meta">
    Run: {{.RunDate}}{{if .RunURL}} &middot; <a href="{{.RunURL}}" target="_blank" rel="noopener">CI run &#8599;</a>{{end}}
  </p>
  <div class="stats">
    <span class="badge full">&#x1F31F; {{.Full}} FULL</span>
    <span class="badge pass">&#x2705; {{.Pass}} PASS</span>
    <span class="badge fail">&#x274C; {{.Fail}} FAIL</span>
    <span class="badge total">{{.Total}} total</span>
  </div>
</header>

<main>

<h2>Results</h2>
{{if .Reports}}
<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th style="width:24px"></th>
      <th>SDK / Instrumentation</th>
      <th>Profile</th>
      <th>Verdict</th>
      <th>Required</th>
      <th>Optional</th>
      <th>Note</th>
      <th>Generated</th>
    </tr>
  </thead>
  <tbody>
  {{range .Reports}}
    <tr class="summary-row" onclick="toggleDetail({{.Index}}, this)">
      <td><span class="toggle">&#x25B6;</span></td>
      <td>
        <span class="sdk">{{.SDK}}</span>
        <span class="instr"> / {{.Instrumentation}}</span>
      </td>
      <td>{{.Profile}}</td>
      <td><span class="verdict-badge verdict-{{lower .Verdict}}">{{.Verdict}}</span></td>
      <td class="count {{if eq .ReqPass .ReqTotal}}ok{{else}}err{{end}}">{{.ReqPass}}/{{.ReqTotal}}</td>
      <td class="count {{if eq .OptPresent .OptTotal}}ok{{else}}warn{{end}}">{{.OptPresent}}/{{.OptTotal}}</td>
      <td>{{if .Note}}<span class="note">{{.Note}}</span>{{end}}</td>
      <td class="gen-at">{{dateOf .GeneratedAt}}</td>
    </tr>
    <tr class="detail-row" id="detail-{{.Index}}" style="display:none">
      <td colspan="8">
        <div class="detail-inner">
          <div class="detail-grid">
            <div class="detail-section">
              <h3>Required Attributes</h3>
              <table class="attr-table">
                <thead><tr><th>Rule</th><th>Attribute</th><th>Status</th><th>Fallback</th></tr></thead>
                <tbody>
                {{range .Required}}
                  <tr>
                    <td>{{.RuleID}}</td>
                    <td><code>{{.Attribute}}</code></td>
                    <td class="s-{{statusClass .Status}}">{{statusIcon .Status}} {{.Status}}</td>
                    <td>{{if .FallbackUsed}}<code>{{.FallbackUsed}}</code>{{end}}</td>
                  </tr>
                {{end}}
                </tbody>
              </table>
            </div>
            <div class="detail-section">
              <h3>Optional Attributes</h3>
              <table class="attr-table">
                <thead><tr><th>Rule</th><th>Attribute</th><th>Status</th></tr></thead>
                <tbody>
                {{range .Optional}}
                  <tr>
                    <td>{{.RuleID}}</td>
                    <td><code>{{.Attribute}}</code></td>
                    <td class="s-{{statusClass .Status}}">{{statusIcon .Status}} {{.Status}}</td>
                  </tr>
                {{end}}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </td>
    </tr>
  {{end}}
  </tbody>
</table>
</div>
{{else}}
<div class="table-wrap">
  <div class="empty-state">No audit reports found for this run.</div>
</div>
{{end}}

{{if .History}}
<h2>Run History</h2>
<div class="table-wrap">
<table class="history-table">
  <thead>
    <tr>
      <th>Date</th>
      <th>FULL</th>
      <th>PASS</th>
      <th>FAIL</th>
      <th>Total</th>
      <th>CI Run</th>
    </tr>
  </thead>
  <tbody>
  {{range .History}}
    <tr>
      <td>{{.Date}}</td>
      <td class="count note">{{.Full}}</td>
      <td class="count ok">{{.Pass}}</td>
      <td class="count err">{{.Fail}}</td>
      <td class="count">{{.Total}}</td>
      <td>{{if .RunURL}}<a href="{{.RunURL}}" target="_blank" rel="noopener">&#8599;</a>{{end}}</td>
    </tr>
  {{end}}
  </tbody>
</table>
</div>
{{end}}

</main>

<footer>
  Generated by report-gen &middot; <a href="https://github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples" target="_blank" rel="noopener">dynatrace-ai-agent-instrumentation-examples</a>
</footer>

<script>
function toggleDetail(idx, row) {
  var detail = document.getElementById('detail-' + idx);
  var visible = detail.style.display !== 'none';
  detail.style.display = visible ? 'none' : 'table-row';
  row.classList.toggle('expanded', !visible);
}
</script>

</body>
</html>`
