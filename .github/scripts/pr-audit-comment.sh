#!/usr/bin/env bash
# Post (or update) a sticky PR comment summarizing the span-audit reports produced
# by the e2e suites that ran for this pull request.
#
# Behavior:
#   0 reports          → short "no suites affected" note
#   1..THRESHOLD        → full report tables inline
#   > THRESHOLD         → each report collapsed in a <details> fold with a verdict
#                         tick in the summary, plus a link to the run for the detail.
#
# The comment is made sticky via a hidden HTML marker: on every push we find the
# existing comment carrying the marker and PATCH it, otherwise we POST a new one.
#
# Inputs (environment variables):
#   GH_TOKEN    - token with pull-requests:write (provided by the workflow)
#   REPO        - owner/repo (github.repository)
#   PR_NUMBER   - pull request number (github.event.pull_request.number)
#   RUN_URL     - URL of this Actions run (linked in the overflow case)
#   REPORTS_DIR - directory containing the merged *.md / *.json reports
set -euo pipefail

THRESHOLD=2
MARKER="<!-- e2e-span-audit-report -->"
REPORTS_DIR="${REPORTS_DIR:-all-reports}"

# Collect report basenames (one per suite) from the JSON files, sorted for a
# stable comment order. JSON is the source of truth for the verdict tick; the
# matching .md holds the human-readable tables.
json_files=()
while IFS= read -r f; do
  [ -n "$f" ] && json_files+=("$f")
done < <(find "$REPORTS_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | sort)
count=${#json_files[@]}

body_file="$(mktemp)"
{
  echo "$MARKER"
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

# Upsert the sticky comment: find an existing comment carrying the marker,
# PATCH it if present, otherwise POST a new one.
existing_id=$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" --paginate \
  --jq ".[] | select(.body | contains(\"${MARKER}\")) | .id" | head -n1 || true)

if [ -n "$existing_id" ]; then
  jq -n --rawfile body "$body_file" '{body: $body}' \
    | gh api -X PATCH "repos/${REPO}/issues/comments/${existing_id}" --input -
  echo "updated comment ${existing_id}"
else
  jq -n --rawfile body "$body_file" '{body: $body}' \
    | gh api -X POST "repos/${REPO}/issues/${PR_NUMBER}/comments" --input -
  echo "created new comment"
fi
