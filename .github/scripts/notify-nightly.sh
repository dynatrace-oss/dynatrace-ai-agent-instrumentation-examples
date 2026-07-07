#!/usr/bin/env bash
# Called by the notify job in e2e.yml after nightly runs complete.
# Required env: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_RUN_ID,
#               CURRENT_ONEAGENT, CURRENT_OTELCOL
set -euo pipefail

REPO="${GITHUB_REPOSITORY}"
CURRENT_RUN_ID="${GITHUB_RUN_ID}"
RUN_URL="https://github.com/${REPO}/actions/runs/${CURRENT_RUN_ID}"

# Determine overall current status
CURRENT_STATUS="success"
FAILING_JOBS=""
if [ "$CURRENT_ONEAGENT" = "failure" ]; then
  CURRENT_STATUS="failure"
  FAILING_JOBS="oneagent-nightly"
fi
if [ "$CURRENT_OTELCOL" = "failure" ]; then
  CURRENT_STATUS="failure"
  FAILING_JOBS="${FAILING_JOBS:+$FAILING_JOBS, }otelcol"
fi

# Fetch previous completed nightly run id + conclusion
PREV_RUN=$(gh api \
  "repos/${REPO}/actions/workflows/e2e.yml/runs?event=schedule&status=completed&per_page=5" \
  --jq ".workflow_runs[] | select(.id != ${CURRENT_RUN_ID}) | {id: .id, conclusion: .conclusion}" \
  | head -1 || true)
PREV_RUN_ID=$(echo "$PREV_RUN" | jq -r '.id // empty')
PREV_CONCLUSION=$(echo "$PREV_RUN" | jq -r '.conclusion // empty')

echo "Previous nightly run: ${PREV_RUN_ID:-unknown} (${PREV_CONCLUSION:-unknown})"
echo "Current nightly status: ${CURRENT_STATUS}"
echo "Failing jobs: ${FAILING_JOBS:-none}"

# Determine event type
EVENT_TYPE=""
if [ "$CURRENT_STATUS" = "failure" ] && [ "$PREV_CONCLUSION" = "success" ]; then
  EVENT_TYPE="regression"
elif [ "$CURRENT_STATUS" = "success" ] && [ "$PREV_CONCLUSION" = "failure" ]; then
  EVENT_TYPE="recovery"
fi

if [ -z "$EVENT_TYPE" ]; then
  echo "No state change detected. Skipping."
  exit 0
fi

# Build attribute diff table by comparing JSON audit reports
DIFF_SECTION=""
if [ -n "${PREV_RUN_ID:-}" ]; then
  mkdir -p curr-reports prev-reports
  gh run download "$CURRENT_RUN_ID" --dir curr-reports --repo "${REPO}" 2>/dev/null || true
  gh run download "$PREV_RUN_ID"    --dir prev-reports --repo "${REPO}" 2>/dev/null || true

  DIFF_ROWS=""
  while IFS= read -r curr_file; do
    filename=$(basename "$curr_file")
    prev_file=$(find prev-reports -name "$filename" | head -1)
    [ -f "$prev_file" ] || continue

    ROWS=$(jq -r '
      def was_ok: test("^(pass|pass_via_fallback|present|present_via_fallback)$");
      def is_bad: test("^(fail|absent)$");
      . as $curr |
      input as $prev |
      ($prev.required + $prev.optional) as $prev_attrs |
      ($curr.required  + $curr.optional)  as $curr_attrs |
      $curr_attrs[] |
      . as $c |
      ($prev_attrs[] | select(.attribute == $c.attribute)) as $p |
      select(($p.status | was_ok) and ($c.status | is_bad)) |
      "| `\($curr.sdk)/\($curr.instrumentation)` | `\(.attribute)` | \($p.status) | \($c.status) |"
    ' "$curr_file" "$prev_file" 2>/dev/null || true)

    DIFF_ROWS="${DIFF_ROWS}${ROWS}"$'\n'
  done < <(find curr-reports -name "*.json")

  if [ -n "${DIFF_ROWS// /}" ]; then
    DIFF_SECTION=$'\n\n## Attribute regressions\n\n| Suite | Attribute | Before | Now |\n|-------|-----------|--------|-----|\n'"${DIFF_ROWS}"
  else
    DIFF_SECTION=$'\n\n_No per-attribute diff available (reports missing or no attribute changes detected)._'
  fi
fi

if [ "$EVENT_TYPE" = "regression" ]; then
  BODY="$(printf '%b' "## Nightly E2E regression\n\nThe nightly run failed after a previously successful run.\n\n**Failing jobs:** ${FAILING_JOBS}\n**Run:** ${RUN_URL}\n**Previous conclusion:** \`${PREV_CONCLUSION}\`${DIFF_SECTION}")"
  gh issue create \
    --title "Nightly E2E regression: ${FAILING_JOBS}" \
    --body "$BODY" \
    --label "nightly-e2e-alert" \
    --repo "${REPO}" || echo "Warning: failed to create GitHub issue"
else
  OPEN_ISSUE=$(gh issue list \
    --label "nightly-e2e-alert" \
    --state open \
    --json number \
    --jq '.[0].number' \
    --repo "${REPO}" || true)
  if [ -n "${OPEN_ISSUE:-}" ]; then
    gh issue close "$OPEN_ISSUE" \
      --comment "$(printf '%b' "## Nightly E2E recovered\n\nThe nightly run is green again.\n\n**Run:** ${RUN_URL}\n**Previous conclusion:** \`${PREV_CONCLUSION}\`")" \
      --repo "${REPO}" || echo "Warning: failed to close GitHub issue"
  else
    echo "No open nightly-e2e-alert issue found to close."
  fi
fi
