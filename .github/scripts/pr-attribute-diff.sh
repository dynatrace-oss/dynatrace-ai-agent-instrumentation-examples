#!/usr/bin/env bash
# Emits a markdown fragment summarizing attribute-level changes between this
# run's span-audit reports and the baseline (last completed nightly run on
# main), so PR reviewers see new / regressed gen_ai.* attributes without
# digging through the full per-suite tables. Written to stdout; the caller
# appends it into the PR comment body.
#
# Reports are matched by filename (`<sdk>-<instrumentation>.json`). An
# attribute only counts as changed if its detection status flips between an
# ok status (pass/pass_via_fallback/present/present_via_fallback) and a bad
# one (fail/absent), in either direction — a rule added or removed by the PR
# itself that was never/still isn't observed doesn't show up.
#
# Inputs (environment variables):
#   CURR_DIR     - directory with this run's *.json span-audit reports
#   BASELINE_DIR - directory with the baseline nightly run's *.json reports
set -euo pipefail

CURR_DIR="${CURR_DIR:-all-reports}"
BASELINE_DIR="${BASELINE_DIR:-baseline-reports}"

if [ ! -d "$BASELINE_DIR" ] || [ -z "$(find "$BASELINE_DIR" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
  echo "_No nightly baseline available to diff attributes against._"
  exit 0
fi

ALL_ROWS=""
while IFS= read -r curr_file; do
  filename=$(basename "$curr_file")
  prev_file=$(find "$BASELINE_DIR" -maxdepth 1 -name "$filename" | head -1)
  [ -n "$prev_file" ] && [ -f "$prev_file" ] || continue

  ROWS=$(jq -r '
    def was_ok: test("^(pass|pass_via_fallback|present|present_via_fallback)$");
    def is_bad: test("^(fail|absent)$");
    def attrs: (.required + .optional + ([.metrics[]? | {attribute: .metric, status: .status}]))
      | map({key: .attribute, value: .status}) | from_entries;
    . as $curr | input as $prev |
    ($curr | attrs) as $c | ($prev | attrs) as $p |
    (($c | keys) + ($p | keys) | unique) as $names |
    $names[] as $name |
    ($c[$name]) as $cs | ($p[$name]) as $ps |
    if ($ps != null and ($ps | was_ok) and ($cs == null or ($cs | is_bad))) then
      "REMOVED\t\($curr.sdk)/\($curr.instrumentation)\t\($name)\t\($ps)\t\($cs // "not tracked")"
    elif (($ps == null or ($ps | is_bad)) and $cs != null and ($cs | was_ok)) then
      "ADDED\t\($curr.sdk)/\($curr.instrumentation)\t\($name)\t\($ps // "not tracked")\t\($cs)"
    else empty end
  ' "$curr_file" "$prev_file" 2>/dev/null || true)

  [ -n "$ROWS" ] && ALL_ROWS="${ALL_ROWS}${ROWS}"$'\n'
done < <(find "$CURR_DIR" -maxdepth 1 -name '*.json' | sort)

ALL_ROWS="${ALL_ROWS%$'\n'}"

if [ -z "$ALL_ROWS" ]; then
  echo "No attribute changes vs. the last nightly run on \`main\`."
  exit 0
fi

print_table() {
  local label="$1" rows="$2"
  [ -z "$rows" ] && return
  echo "**${label}**"
  echo
  echo "| Suite | Attribute | Before | Now |"
  echo "|-------|-----------|--------|-----|"
  echo "$rows" | awk -F'\t' '{printf "| `%s` | `%s` | %s | %s |\n", $2, $3, $4, $5}'
  echo
}

print_table "➕ Added" "$(echo "$ALL_ROWS" | awk -F'\t' '$1=="ADDED"')"
print_table "➖ Removed" "$(echo "$ALL_ROWS" | awk -F'\t' '$1=="REMOVED"')"
