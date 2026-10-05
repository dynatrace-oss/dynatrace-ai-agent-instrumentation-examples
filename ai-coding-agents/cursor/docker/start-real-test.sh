#!/usr/bin/env bash
set -euo pipefail

if [ -z "${CURSOR_API_KEY:-}" ]; then
  echo "ERROR: CURSOR_API_KEY is not set. Provide it via --env-file or env var." >&2
  exit 2
fi

echo "=== start-real-test: Begin ==="

# Candidate CA bundle / installer handling left as before (assume handled prior)
CA_PATH="/etc/ssl/certs/ca-certificates.crt"
export SSL_CERT_FILE="$CA_PATH"
export CURL_CA_BUNDLE="$CA_PATH"

run_installer() {
  if [ -n "${FOUND_CA:-}" ]; then
    curl --cacert "$FOUND_CA" -fsS https://cursor.com/install | bash -s -- -y 2>&1 | tee /tmp/cursor-installer.log
  else
    curl -fsS https://cursor.com/install | bash -s -- -y 2>&1 | tee /tmp/cursor-installer.log
  fi
}

# Try to install if agent not already present in PATH
if command -v agent >/dev/null 2>&1; then
  echo "agent already available in PATH: $(command -v agent)"
else
  echo "Installing Cursor CLI at runtime..."
  # run installer and capture output; if it fails, dump log
  if ! run_installer; then
    echo "ERROR: Cursor installer failed. Dumping /tmp/cursor-installer.log:" >&2
    sed -n '1,200p' /tmp/cursor-installer.log >&2 || true
    echo "Listing /etc/ssl and /etc/ssl/certs for debug:" >&2
    ls -la /etc/ssl || true
    ls -la /etc/ssl/certs || true
    exit 3
  fi
fi

echo "Installer finished — locating 'agent' binary (best-effort)..."

# Candidate locations the installer commonly uses
CANDIDATE_AGENTS=(
  "/root/.cursor/bin/agent"
  "/root/.local/bin/agent"
  "/root/.local/bin/cursor"
  "/root/.local/bin/agent.exe"
  "/usr/local/bin/agent"
  "/usr/bin/agent"
  "/opt/cursor/bin/agent"
  "$HOME/.local/bin/agent"
)

FOUND_AGENT=""
for p in "${CANDIDATE_AGENTS[@]}"; do
  if [ -x "$p" ]; then
    FOUND_AGENT="$p"
    break
  fi
done

# Also try which/command as a fallback (installer may have added to PATH)
if [ -z "$FOUND_AGENT" ]; then
  if command -v agent >/dev/null 2>&1; then
    FOUND_AGENT="$(command -v agent)"
  fi
fi

if [ -n "$FOUND_AGENT" ]; then
  echo "Found agent at: $FOUND_AGENT"
  # Ensure it's on PATH (add its dir)
  AGENT_DIR="$(dirname "$FOUND_AGENT")"
  export PATH="$AGENT_DIR:$PATH"
  echo "PATH updated to include $AGENT_DIR"
  # Create a stable symlink so scripts can use 'agent'
  if [ ! -x "/usr/local/bin/agent" ]; then
    ln -sf "$FOUND_AGENT" /usr/local/bin/agent || true
  fi
else
  echo "ERROR: 'agent' not found in any standard location." >&2
  echo "Installer log (/tmp/cursor-installer.log):" >&2
  sed -n '1,200p' /tmp/cursor-installer.log >&2 || true
  echo "Directory dumps for debugging:" >&2
  ls -la /root || true
  ls -la /root/.local || true
  ls -la /root/.cursor || true
  ls -la /usr/local/bin || true
  echo "If the installer suggested adding ~/.local/bin to your PATH, the agent may be at /root/.local/bin/agent." >&2
  exit 4
fi

# --- Proceed with workspace and agent run (same as before) ---
echo "Preparing workspace..."
cp -R /workspace/seed/. /workspace/
cd /workspace

git init -q
git config user.email "cursor-otel-test@example.invalid"
git config user.name "Cursor OTel Test"
git add .
git commit -qm "Seed intentionally broken cart kata" || true

echo "Running agent with model: ${CURSOR_MODEL:-auto}"
if ! command -v agent >/dev/null 2>&1; then
  echo "ERROR: 'agent' not found in PATH after installation and path fixes." >&2
  ls -la /root/.local || true
  ls -la /root/.cursor || true
  exit 5
fi

agent -p --force --model "${CURSOR_MODEL:-auto}" --output-format stream-json \
  "Work in this repository. Read README.md and the existing tests. Run the tests, diagnose the implementation bugs, fix src/cart.js, add at least two meaningful edge-case tests, run npm test until it passes, and write REVIEW.md summarizing the changes. Do not access files outside this repository."

echo "Verifying repository after Cursor completed"
npm test
if [ ! -f REVIEW.md ]; then
  echo "ERROR: REVIEW.md not found after agent run" >&2
  exit 6
fi

echo "=== start-real-test: Completed successfully ==="