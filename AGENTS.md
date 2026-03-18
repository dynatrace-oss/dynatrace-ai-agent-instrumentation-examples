# Agent Instructions

Use `dtctl` to validate all changes against a live Dynatrace environment. Do not rely on static review alone.

## Rules

1. **After running any `test_connection.py`**, confirm data landed: `dtctl query "fetch logs | filter service.name == '<service>' | limit 5" -o json --plain`
2. **After changing a dashboard JSON**, apply it: `dtctl apply -f <file>.json --plain` and verify with `dtctl get dashboards --mine -o json --plain`
3. **Before committing any DQL**, run it: `dtctl query "<dql>" -o json --plain`
4. **When adding a new integration**, run steps 1–3 for all signals (metrics, logs, traces) and all dashboard tiles
5. **Check your context before starting**: `dtctl config current-context && dtctl auth whoami --plain`

## Reference

- Full dtctl command syntax → [`SKILL.md`](SKILL.md)
- Dashboard YAML schema → [`references/resources/dashboards.md`](references/resources/dashboards.md)
- Troubleshooting / install → [`references/troubleshooting.md`](references/troubleshooting.md)
