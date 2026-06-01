---
name: dynatrace-control
description: Manage Dynatrace environments using dtctl - install/update the CLI, configure authentication with OS keyring tokens, and run kubectl-style operations (get/describe/edit/apply/delete/query/exec) for workflows, dashboards, notebooks, DQL, SLOs, settings, buckets, lookups, OpenPipeline, and Davis AI. Use when the user wants to control Dynatrace resources via dtctl.
---

# Dynatrace Control with dtctl

Operate `dtctl`, the kubectl-style CLI for Dynatrace. This skill teaches core dtctl command patterns and operations.

## Skill Initialization

**CRITICAL**: When this skill is loaded, IMMEDIATELY run these commands to display the current context:

```bash
# Show current context
dtctl config current-context

# Show context details
dtctl config describe-context $(dtctl config current-context) --plain

# Show authenticated user
dtctl auth whoami --plain
```

This displays:
- Current context name and environment URL
- Safety level (readonly, readwrite-mine, readwrite-all, dangerously-unrestricted)
- Authenticated user identity (name, email, UUID)

## Prerequisites

If dtctl is not installed or not working, see [references/troubleshooting.md](references/troubleshooting.md) for installation and setup.

## Resources & Commands

### Available Resources

dtctl manages these resource types. **Before using a resource, read its reference doc** to understand field names, JSON structure, and filtering patterns.

| Resource | Aliases | Reference Documentation |
|----------|---------|------------------------|
| analyzer | analyzers | [analyzers.md](references/resources/analyzers.md) - Davis AI analyzers |
| app | apps | [apps.md](references/resources/apps.md) - Applications |
| bucket | bkt | [buckets.md](references/resources/buckets.md) - Data buckets |
| copilot-skill | copilot-skills | [copilot-skills.md](references/resources/copilot-skills.md) - Davis CoPilot skills |
| dashboard | dash | [dashboards.md](references/resources/dashboards.md) - Dashboards (use `.name` NOT `.title`) |
| edgeconnect | ec | [edgeconnect.md](references/resources/edgeconnect.md) - EdgeConnect |
| function | functions, fn, func | [functions.md](references/resources/functions.md) - App Engine functions |
| group | groups | [groups.md](references/resources/groups.md) - User groups |
| intent | intents | [intents.md](references/resources/intents.md) - App intents |
| lookup | lookups | [lookups.md](references/resources/lookups.md) - Lookup tables |
| notebook | nb | [notebooks.md](references/resources/notebooks.md) - Notebooks |
| notification | notifications | [notifications.md](references/resources/notifications.md) - Event notifications |
| sdk-version | sdk-versions | [sdk-versions.md](references/resources/sdk-versions.md) - SDK versions |
| settings | setting | [settings.md](references/resources/settings.md) - Settings objects |
| settings-schema | schema | [settings-schema.md](references/resources/settings-schema.md) - Settings schemas |
| slo | - | [slo.md](references/resources/slo.md) - Service Level Objectives |
| slo-template | slo-templates | [slo-templates.md](references/resources/slo-templates.md) - SLO templates |
| trash | deleted | [trash.md](references/resources/trash.md) - Trashed documents |
| user | users | [users.md](references/resources/users.md) - Users |
| workflow | wf | [workflows.md](references/resources/workflows.md) - Workflows |
| workflow-execution | wfe | [workflow-execution.md](references/resources/workflow-execution.md) - Workflow executions |

### Command Verbs

| Verb | Description | Example |
|------|-------------|---------|
| **get** | List resources | `dtctl get workflows --mine` |
| **describe** | Show resource details | `dtctl describe workflow <id>` |
| **edit** | Edit resource interactively | `dtctl edit dashboard <id>` |
| **apply** | Create/update from file | `dtctl apply -f workflow.yaml --set env=prod` |
| **delete** | Delete resource | `dtctl delete workflow <id>` |
| **exec** | Execute workflow/function/analyzer/copilot | `dtctl exec workflow <id>` |
| **query** | Run DQL query | `dtctl query "fetch logs \| limit 10"` |
| **logs** | Print resource logs | `dtctl logs workflow-execution <id>` |
| **wait** | Wait for conditions | `dtctl wait query "fetch logs" --for=any` |
| **history** | Show document history | `dtctl history dashboard <id>` |
| **restore** | Restore document version | `dtctl restore dashboard <id> --version 3` |
| **share** | Share document | `dtctl share dashboard <id> --user email@example.com` |
| **unshare** | Remove sharing | `dtctl unshare dashboard <id> --user email@example.com` |
| **find** | Discover resources | `dtctl find intents --data trace.id=abc` |
| **open** | Open in browser | `dtctl open intent <app/intent> --data key=value` |
| **diff** | Compare resources | `dtctl diff -f workflow.yaml` |

**For detailed command usage**, see:
- [references/commands.md](references/commands.md) - All command patterns and examples
- [references/copilot.md](references/copilot.md) - Davis CoPilot commands
- [references/functions.md](references/functions.md) - Function execution
- [references/analyzers-usage.md](references/analyzers-usage.md) - Analyzer execution

## Key Concepts for AI Agents

### Output Modes

```bash
# Machine-readable formats (use these for AI agents)
-o json          # JSON output
-o yaml          # YAML output
-o csv           # CSV output
-o chart         # ASCII chart (for time series)
-o sparkline     # ASCII sparkline (for time series)
-o barchart      # ASCII bar chart (for time series)

# Human-readable formats
-o table         # Table format (default)
-o wide          # Wide table with more columns

# Always use --plain flag for AI consumption
--plain          # Strips colors and prompts, best for parsing
```

**For AI agents, always use:** `dtctl <command> -o json --plain`

### Template Variables

In YAML/DQL files, use Go template syntax:

```yaml
# workflow.yaml
title: "{{.environment}} Deployment"
owner: "{{.team}}"
trigger:
  schedule:
    cron: "{{.schedule | default "0 0 * * *"}}"
```

```dql
# query.dql
fetch logs
| filter host.name == "{{.host}}"
| filter timestamp > now() - {{.timerange | default "1h"}}
```

Execute with: `dtctl apply -f file.yaml --set environment=prod --set team=platform`

### Authentication & Permissions

```bash
# Check current user and permissions
dtctl auth whoami --plain
dtctl auth can-i create workflows
dtctl auth can-i delete dashboards
```

Use `can-i` to verify permissions before attempting operations.

## Quick Reference: DQL Queries

```bash
# Inline query
dtctl query "fetch logs | filter status='ERROR' | limit 100" -o json --plain

# Query from file with variables
dtctl query -f query.dql --set host=h-123 --set timerange=2h -o json --plain

# Wait for query results
dtctl wait query "fetch spans | filter test_id='test-123'" --for=count=1 --timeout 5m

# Query with chart output
dtctl query "timeseries avg(dt.host.cpu.usage)" -o chart --plain
```

**For more DQL patterns**, see [dt-dql-helpers skill](../dt-dql-helpers/SKILL.md) or load that skill.

## Dashboards

Create/update: `dtctl apply -f dashboard.yaml --plain`. Export for reference: `dtctl get dashboard <id> -o yaml --plain`.

### YAML skeleton

```yaml
name: "Dashboard Name"
type: dashboard
content:
  annotations: []
  importedWithCode: false
  settings:
    defaultTimeframe:
      enabled: true
      value: { from: now()-2h, to: now() }
  layouts:
    "1":                    # string key, must match a tile key
      x: 0                 # 24-column grid (full=24, half=12, third=8)
      "y": 0               # MUST quote "y" to avoid YAML boolean parse
      w: 12
      h: 6
  tiles:
    "1":
      title: "Tile Title"
      type: data            # data | markdown
      query: |
        fetch logs | limit 10
      visualization: lineChart
      visualizationSettings:
        autoSelectVisualization: false
      davis: { enabled: false, davisVisualization: { isAvailable: true } }
```

### Tile types & visualizations

- **`type: data`** — DQL tile with `query` + `visualization`: `singleValue`, `lineChart`, `areaChart`, `barChart`, `pieChart`, `table`, `honeycomb`, `scatterplot`
- **`type: markdown`** — static text via `content` field (supports markdown)

### Key visualizationSettings patterns

**singleValue** — `recordField` must match query alias:
```yaml
singleValue: { showLabel: true, label: "Errors", recordField: errors }
```

**Charts** (line/area/bar):
```yaml
chartSettings: { legend: { position: bottom, showLegend: true }, stacked: true }
axes: { yAxis: { label: "CPU %" } }
```

**Table** — column keys use `'["field"]'` format:
```yaml
table: { linewrapEnabled: true, columnWidths: { '["content"]': 500 } }
```

**Unit overrides** (durations):
```yaml
unitsOverrides: [{ identifier: p99, baseUnit: nanosecond, displayUnit: null, decimals: 1 }]
```

**Thresholds** (color rules, comparators: `<=`, `>=`, `=`, `<`, `>`):
```yaml
thresholds:
  - field: errors
    id: 1
    isEnabled: true
    rules:
      - { color: { Default: "var(--dt-colors-charts-status-ideal-default, #2f6862)" }, comparator: "<=", id: 0, value: 100 }
      - { color: { Default: "var(--dt-colors-charts-status-warning-default, #eea53c)" }, comparator: "<=", id: 1, value: 500 }
      - { color: { Default: "var(--dt-colors-charts-status-critical-default, #c62239)" }, comparator: ">", id: 2, value: 500 }
```

### Gotchas
- Always set `davis.enabled: false` on data tiles.
- Use `makeTimeseries` for log/span time series; `timeseries` for metrics.
- `version` field warning on create is benign.
- No `id` field → creates new; with `id` field → updates existing.

## Common Issues

**Name resolution ambiguity:**
- If a name matches multiple resources, dtctl will fail
- Solution: Use IDs instead of names
- Find ID: `dtctl get <resource> -o json --plain | jq -r '.[] | "\(.id) | \(.name)"'`

**Permission denied:**
- Check token scopes: https://github.com/dynatrace-oss/dtctl/blob/main/docs/TOKEN_SCOPES.md
- Verify permissions: `dtctl auth can-i <verb> <resource>`
- Check safety level: `dtctl config describe-context $(dtctl config current-context) --plain`

**Context/safety blocks:**
- Destructive operations may be blocked by safety level
- Switch context: `dtctl config use-context <name>`
- Adjust safety level when creating context

## Additional Resources

- **Troubleshooting**: [references/troubleshooting.md](references/troubleshooting.md)
- **Multi-tenant setup**: [references/config-management.md](references/config-management.md)
- **All commands**: [references/commands.md](references/commands.md)
- **CLI help**: `dtctl --help`, `dtctl <command> --help`

## Safety Reminders

- Use `--plain` for machine/AI consumption
- Confirm context + safety level before destructive ops; prefer `get/describe` first
- Use `--mine` flag to filter resources you own
- For multi-tenant work, see [references/config-management.md](references/config-management.md)
