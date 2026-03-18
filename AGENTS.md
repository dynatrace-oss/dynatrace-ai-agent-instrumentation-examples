# Agent Instructions

This file guides AI agents (Claude Code, OpenAI Codex, Gemini CLI, GitHub Copilot, and others) on how to validate and test changes in this repository.

## Core Principle: Validate Against the Real Platform

This repository produces artifacts that must work against a live Dynatrace environment — OTLP setup scripts, dashboard JSON files, DQL queries, monitoring matrices, and connection test scripts. **Do not rely on static review alone.** Use `dtctl` to validate every change against the actual platform before considering work complete.

`dtctl` is a kubectl-style CLI for Dynatrace. It lets agents interact with the platform without a browser: run DQL queries, apply dashboards, inspect ingested data, validate settings, and test workflows entirely from the terminal.

### Initialize your context first

Before any validation work, confirm which environment you are targeting:

```bash
dtctl config current-context
dtctl config describe-context $(dtctl config current-context) --plain
dtctl auth whoami --plain
```

If `dtctl` is not installed or configured, see [`references/troubleshooting.md`](references/troubleshooting.md).

---

## Validation Scenarios

### 1. Validating OTLP Data Ingest

Each integration in this repo includes a `test_connection.py` (or equivalent) that sends sample telemetry. After running it, verify the data actually landed in Dynatrace using DQL.

**Check that metrics arrived:**

```bash
# Replace 'codex_cli_rs' with the service.name from the integration under test
dtctl query "fetch metrics | filter dt.entity.service == 'codex_cli_rs' | limit 5" -o json --plain

# Or query by metric key prefix
dtctl query "fetch metrics | filter metricKey startsWith 'codex.' | limit 20" -o json --plain
```

**Check that logs arrived:**

```bash
dtctl query "fetch logs | filter service.name == 'codex_cli_rs' | sort timestamp desc | limit 20" -o json --plain
```

**Check that traces/spans arrived:**

```bash
dtctl query "fetch spans | filter service.name == 'codex_cli_rs' | sort timestamp desc | limit 10" -o json --plain
```

**Validate specific event names** (e.g. from a monitoring matrix):

```bash
dtctl query "fetch logs | filter event.name == 'codex.conversation_starts' | limit 5" -o json --plain
```

**Expected result:** Records are returned. If the query returns zero rows within 2–3 minutes of the test script finishing, the ingest pipeline or credentials are broken.

---

### 2. Validating and Applying Dashboard JSON Files

Each integration ships a `*-monitoring-dashboard.json`. Before committing changes to a dashboard file, apply it to Dynatrace and verify it renders without errors.

**Apply a dashboard:**

```bash
dtctl apply -f openai-codex/codex-monitoring-dashboard.json --plain
```

**Verify it was created/updated:**

```bash
dtctl get dashboards --mine -o json --plain | jq -r '.[] | "\(.id) \(.name)"'
```

**Inspect the applied result:**

```bash
dtctl describe dashboard <id> -o json --plain
```

**Spot-check the tiles execute without error** by running each tile's DQL query directly:

```bash
dtctl query "fetch metrics | filter metricKey startsWith 'codex.' | summarize count()" -o json --plain
```

**What to look for:**
- `dtctl apply` exits 0 and returns the dashboard ID
- No tile has a DQL syntax error (test the tile queries independently if unsure)
- The dashboard appears in `dtctl get dashboards --mine`

---

### 3. Validating DQL Queries

Any DQL that appears in a dashboard tile, notebook, monitoring matrix, or documentation must be tested with real data before merging.

**Run a query directly:**

```bash
dtctl query "fetch logs | filter service.name == 'claude_code' | limit 10" -o json --plain
```

**Validate query syntax without full execution** (useful for complex queries):

```bash
dtctl query "fetch spans | filter service.name == 'gemini-cli' | summarize count() by bin(timestamp, 5m)" -o json --plain
```

**Test time-series queries** (used in line/area chart tiles):

```bash
dtctl query "timeseries avg(dt.host.cpu.usage), by: {service.name}" -o chart --plain
```

**Common DQL mistakes to validate:**
- Field names in `filter` clauses match what the integration actually sends (check against `test_connection.py` attribute maps)
- `makeTimeseries` vs `timeseries` — use `timeseries` for metrics, `makeTimeseries` for logs/spans
- Aggregation aliases match `singleValue` tile `recordField` settings in the dashboard JSON

---

### 4. Validating OTLP Endpoint and Token Configuration

When a contributor adds or changes endpoint/token setup (e.g. in `setup.sh` or `.env.example`):

**Pre-flight check via dtctl auth:**

```bash
dtctl auth whoami --plain
dtctl auth can-i create dashboards
dtctl auth can-i ingest metrics
```

**Verify the endpoint URL format is correct** — Dynatrace OTLP base URL must be:

```
https://<env-id>.live.dynatrace.com/api/v2/otlp
```

Not ending in `/v1/traces`, `/v1/metrics`, or `/v1/logs` — the integration scripts strip those suffixes, but documentation and `.env.example` files must show the correct base form.

---

### 5. Validating Metric Schema and Attribute Names

When adding a new integration or extending an existing one, confirm that the metric and attribute names sent by the test script match what DQL can query.

**List all metric keys containing a prefix:**

```bash
dtctl query "fetch metrics | filter metricKey startsWith 'codex.' | fields metricKey | dedup metricKey" -o json --plain
```

**Inspect attribute dimensions on a specific metric:**

```bash
dtctl query "fetch metrics | filter metricKey == 'codex.tool.call' | fields dimensions | limit 5" -o json --plain
```

**Cross-check against the monitoring matrix** — each `monitoring-targets/*.md` file lists expected metric keys and log event names. Run DQL queries for each listed item to confirm they arrive with the expected schema.

---

### 6. Validating Log Event Schema

Each integration sends structured log events. Validate that the event body matches the schema described in the monitoring matrix or README.

**Sample log events and inspect fields:**

```bash
dtctl query "fetch logs | filter service.name == 'codex_cli_rs' | fields timestamp, event.name, conversation.id, model | limit 10" -o json --plain
```

**Check for required fields being present:**

```bash
dtctl query "fetch logs | filter service.name == 'codex_cli_rs' AND isNull(conversation.id) | limit 5" -o json --plain
```

An empty result means `conversation.id` is always populated — good. A non-empty result means the field is missing from some events and the test script or integration code needs fixing.

---

### 7. Applying and Validating Settings / OpenPipeline Config

If a contribution modifies or adds Dynatrace Settings (ingest rules, OpenPipeline, bucket config, etc.):

**Preview the diff before applying:**

```bash
dtctl diff -f settings-file.yaml --plain
```

**Apply the settings:**

```bash
dtctl apply -f settings-file.yaml --plain
```

**Retrieve and inspect the current value:**

```bash
dtctl get settings --schema builtin:openpipeline.logs.pipelines -o json --plain
```

---

### 8. Verifying SLOs (if added)

If a contribution includes an SLO definition:

```bash
dtctl apply -f slo.yaml --plain
dtctl get slos --mine -o json --plain
dtctl describe slo <id> -o json --plain
```

---

### 9. Smoke-Testing a New Integration End-to-End

When a completely new framework integration is added (new top-level folder), run this sequence:

1. **Configure credentials** — copy `.env.example` to `.env`, fill in `DT_API_TOKEN` and `DT_OTEL_ENDPOINT`
2. **Run the setup script** — `source setup.sh`
3. **Run the connection test** — `python3 test_connection.py` (or language equivalent)
4. **Wait ~2 minutes**, then query for ingested data:
   ```bash
   dtctl query "fetch logs | filter service.name == '<new-service-name>' | limit 5" -o json --plain
   dtctl query "fetch metrics | filter metricKey startsWith '<new-prefix>.' | limit 5" -o json --plain
   ```
5. **Apply the dashboard** — `dtctl apply -f <new>-monitoring-dashboard.json --plain`
6. **Spot-check at least one tile's DQL** directly with `dtctl query`

All six steps must succeed before the PR is ready for review.

---

## Output Tips for AI Agents

Always use `--plain` to strip colors and interactive prompts, and `-o json` for parseable output:

```bash
dtctl query "..." -o json --plain
dtctl get dashboards -o json --plain
dtctl describe dashboard <id> -o json --plain
```

Pipe to `jq` for field extraction:

```bash
dtctl get dashboards --mine -o json --plain | jq -r '.[] | "\(.id) \(.name)"'
```

## Further Reference

- [`SKILL.md`](SKILL.md) — full dtctl command reference, dashboard YAML schema, and common patterns
- [`references/commands.md`](references/commands.md) — all dtctl command verbs with examples
- [`references/troubleshooting.md`](references/troubleshooting.md) — installation, auth, and context setup
- [`references/resources/dashboards.md`](references/resources/dashboards.md) — dashboard resource schema
- [`references/resources/settings.md`](references/resources/settings.md) — settings resource schema
