#!/usr/bin/env bash
# Called by the notify job in e2e.yml after nightly runs complete.
# Alerts on two independent conditions:
#   1. Job failure (no spans found — t.Fatalf in test)
#   2. Attribute regression (attribute present before, missing now)
# Required env: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_RUN_ID,
#               CURRENT_ONEAGENT, CURRENT_OTELCOL
set -euo pipefail

REPO="${GITHUB_REPOSITORY}"
CURRENT_RUN_ID="${GITHUB_RUN_ID}"
RUN_URL="https://github.com/${REPO}/actions/runs/${CURRENT_RUN_ID}"

# --- Job-level failure check ---
FAILING_JOBS=""
[ "${CURRENT_ONEAGENT:-}" = "failure" ] && FAILING_JOBS="oneagent-nightly"
[ "${CURRENT_OTELCOL:-}"  = "failure" ] && FAILING_JOBS="${FAILING_JOBS:+$FAILING_JOBS, }otelcol"

# --- Attribute diff ---
PREV_RUN=$(gh api \
  "repos/${REPO}/actions/workflows/e2e.yml/runs?event=schedule&status=completed&per_page=5" \
  --jq ".workflow_runs[] | select(.id != ${CURRENT_RUN_ID}) | {id: .id, conclusion: .conclusion}" \
  | head -1 || true)
PREV_RUN_ID=$(echo "$PREV_RUN" | jq -r '.id // empty')
PREV_CONCLUSION=$(echo "$PREV_RUN" | jq -r '.conclusion // empty')

echo "Previous nightly run: ${PREV_RUN_ID:-unknown} (${PREV_CONCLUSION:-unknown})"
echo "Failing jobs: ${FAILING_JOBS:-none}"

DIFF_ROWS=""
if [ -n "${PREV_RUN_ID:-}" ]; then
  mkdir -p curr-reports prev-reports
  gh run download "$CURRENT_RUN_ID" --dir curr-reports --repo "${REPO}" 2>/dev/null || true
  gh run download "$PREV_RUN_ID"    --dir prev-reports --repo "${REPO}" 2>/dev/null || true

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
fi

HAS_JOB_FAILURE=false
[ -n "${FAILING_JOBS:-}" ] && HAS_JOB_FAILURE=true

HAS_ATTR_REGRESSION=false
[ -n "${DIFF_ROWS// /}" ] && HAS_ATTR_REGRESSION=true

echo "Job failure: ${HAS_JOB_FAILURE} | Attribute regression: ${HAS_ATTR_REGRESSION}"

OPEN_ISSUE=$(gh issue list \
  --label "nightly-e2e-alert" \
  --state open \
  --json number \
  --jq '.[0].number' \
  --repo "${REPO}" || true)

# Build issue body sections
BODY_PARTS=""

if [ "$HAS_JOB_FAILURE" = "true" ]; then
  BODY_PARTS="${BODY_PARTS}$(printf '%b' "## Test failure\n\nOne or more jobs failed (no spans received).\n\n**Failing jobs:** ${FAILING_JOBS}\n")"
fi

if [ "$HAS_ATTR_REGRESSION" = "true" ]; then
  ATTR_TABLE="$(printf '%b' "\n## Attribute regressions\n\nOne or more attributes present in the previous run are now missing.\n\n| Suite | Attribute | Before | Now |\n|-------|-----------|--------|-----|\n${DIFF_ROWS}")"
  BODY_PARTS="${BODY_PARTS}${ATTR_TABLE}"
fi

if [ "$HAS_JOB_FAILURE" = "true" ] || [ "$HAS_ATTR_REGRESSION" = "true" ]; then
  BODY="$(printf '%b' "**Run:** ${RUN_URL}\n**Previous run:** ${PREV_RUN_ID:-unknown}\n\n${BODY_PARTS}")"

  if [ -n "${OPEN_ISSUE:-}" ]; then
    gh issue comment "$OPEN_ISSUE" \
      --body "$BODY" \
      --repo "${REPO}" || echo "Warning: failed to comment on GitHub issue"
  else
    TITLE="Nightly E2E alert"
    [ "$HAS_JOB_FAILURE" = "true" ] && [ "$HAS_ATTR_REGRESSION" = "false" ] && TITLE="Nightly E2E test failure: ${FAILING_JOBS}"
    [ "$HAS_JOB_FAILURE" = "false" ] && [ "$HAS_ATTR_REGRESSION" = "true" ]  && TITLE="Nightly E2E attribute regression"
    gh issue create \
      --title "$TITLE" \
      --body "$BODY" \
      --label "nightly-e2e-alert" \
      --repo "${REPO}" || echo "Warning: failed to create GitHub issue"
  fi
else
  if [ -n "${OPEN_ISSUE:-}" ]; then
    gh issue close "$OPEN_ISSUE" \
      --comment "$(printf '%b' "## Nightly E2E recovered\n\nAll tests pass and all previously missing attributes are present again.\n\n**Run:** ${RUN_URL}")" \
      --repo "${REPO}" || echo "Warning: failed to close GitHub issue"
  else
    echo "All clear. No open issue to close."
  fi
fi
