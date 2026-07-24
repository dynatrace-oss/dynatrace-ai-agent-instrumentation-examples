#!/usr/bin/env bash
# Build the body of the sticky PR comment summarizing the span-audit reports
# produced by the e2e suites that ran for this pull request. The stickiness
# (find/create/update a single comment) is handled by the
# marocchino/sticky-pull-request-comment action; this script only writes the
# comment body to OUTPUT_FILE.
#
# Behavior:
#   0 reports          → short "no suites affected" note
#   1..THRESHOLD        → full report tables inline
#   > THRESHOLD         → each report collapsed in a <details> fold with a verdict
#                         tick in the summary, plus a link to the run for the detail.
#
# Inputs (environment variables):
#   RUN_URL     - URL of this Actions run (linked in the overflow case)
#   REPORTS_DIR - directory containing the merged *.md / *.json reports
#   OUTPUT_FILE - path to write the comment body to (default: comment.md)
set -euo pipefail

THRESHOLD=2
REPORTS_DIR="${REPORTS_DIR:-all-reports}"
OUTPUT_FILE="${OUTPUT_FILE:-comment.md}"

# Collect report basenames (one per suite) from the JSON files, sorted for a
# stable comment order. JSON is the source of truth for the verdict tick; the
# matching .md holds the human-readable tables.
json_files=()
while IFS= read -r f; do
  [ -n "$f" ] && json_files+=("$f")
done < <(find "$REPORTS_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | sort)
count=${#json_files[@]}

body_file="$OUTPUT_FILE"
: > "$body_file"
{
  echo "## 🔭 GenAI span audit"
  echo
} > "$body_file"

verdict_tick() {
  case "$1" in
    FULL) printf '🌟' ;;
    PASS) printf '✅' ;;
    FAIL) printf '❌' ;;
    *)    printf '⚪' ;;
  esac
}

if [ "$count" -eq 0 ]; then
  {
    echo "No e2e suites were affected by this PR, so no span-audit reports were generated."
    echo
    echo "_(Suites run only when their demo directory, test file, or shared e2e infrastructure changes.)_"
  } >> "$body_file"

elif [ "$count" -le "$THRESHOLD" ]; then
  # Few suites: inline the full report tables.
  for jf in "${json_files[@]}"; do
    md="${jf%.json}.md"
    if [ -f "$md" ]; then
      cat "$md" >> "$body_file"
      echo >> "$body_file"
      echo "---" >> "$body_file"
      echo >> "$body_file"
    fi
  done
  echo "[View full run details](${RUN_URL})" >> "$body_file"

else
  # Many suites: collapse each report, with a verdict tick in the summary line.
  {
    echo "${count} suites ran. [View full run details](${RUN_URL})"
    echo
  } >> "$body_file"
  for jf in "${json_files[@]}"; do
    md="${jf%.json}.md"
    sdk=$(jq -r '.sdk // "?"' "$jf")
    instr=$(jq -r '.instrumentation // "?"' "$jf")
    verdict=$(jq -r '.verdict // "?"' "$jf")
    tick=$(verdict_tick "$verdict")
    {
      echo "<details>"
      echo "<summary>${tick} <strong>${sdk} / ${instr}</strong> — ${verdict}</summary>"
      echo
      if [ -f "$md" ]; then
        cat "$md"
      else
        echo "_report markdown not found_"
      fi
      echo
      echo "</details>"
      echo
    } >> "$body_file"
  done
fi

echo "wrote comment body to ${body_file} (${count} reports)"
