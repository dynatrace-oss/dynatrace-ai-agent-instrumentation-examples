#!/usr/bin/env bash
# Downloads the span-audit-report artifacts from the most recently completed
# nightly (schedule-triggered) e2e run on main, so pr-attribute-diff.sh can
# diff this PR's attribute results against that baseline.
#
# Required env: GH_TOKEN, REPO
# Optional env: BASELINE_DIR (default: baseline-reports)
# Outputs (GITHUB_OUTPUT): run_id, run_url — left unset if no baseline was found
set -euo pipefail

REPO="${REPO:?REPO is required}"
BASELINE_DIR="${BASELINE_DIR:-baseline-reports}"
mkdir -p "$BASELINE_DIR"

RUN_JSON=$(gh api \
  "repos/${REPO}/actions/workflows/e2e.yml/runs?event=schedule&branch=main&status=completed&per_page=1" \
  --jq '.workflow_runs[0] // empty')

if [ -z "$RUN_JSON" ]; then
  echo "No completed nightly run found on main; skipping baseline diff."
  exit 0
fi

RUN_ID=$(echo "$RUN_JSON" | jq -r '.id')
RUN_URL=$(echo "$RUN_JSON" | jq -r '.html_url')
echo "Baseline nightly run: ${RUN_ID} (${RUN_URL})"

if ! gh run download "$RUN_ID" --repo "$REPO" --dir "$BASELINE_DIR" --pattern 'span-audit-reports-*' 2>/dev/null; then
  echo "Warning: failed to download baseline artifacts for run ${RUN_ID} (may have expired)"
  exit 0
fi

# gh run download puts each matched artifact in its own subdirectory; flatten
# so pr-attribute-diff.sh can glob *.json directly in BASELINE_DIR.
find "$BASELINE_DIR" -mindepth 2 -name '*.json' -exec mv {} "$BASELINE_DIR" \;

{
  echo "run_id=${RUN_ID}"
  echo "run_url=${RUN_URL}"
} >> "$GITHUB_OUTPUT"
