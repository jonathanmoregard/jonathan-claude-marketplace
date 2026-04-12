#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing detect-secrets ==="

# Check if detect-secrets is installed
if ! command -v detect-secrets &> /dev/null; then
  echo "Installing detect-secrets..."
  pip install detect-secrets || pip3 install detect-secrets
  echo "detect-secrets installed."
else
  echo "detect-secrets already installed."
fi

# Set up global git hooks directory
GLOBAL_HOOKS_DIR="$HOME/.git-hooks"
mkdir -p "$GLOBAL_HOOKS_DIR"

# Write the pre-commit hook
PRE_COMMIT="$GLOBAL_HOOKS_DIR/pre-commit"

# If pre-commit hook already exists, check if it already has detect-secrets
if [ -f "$PRE_COMMIT" ] && grep -q "detect-secrets" "$PRE_COMMIT"; then
  echo "detect-secrets pre-commit hook already installed."
else
  # Append to existing hook or create new one
  if [ -f "$PRE_COMMIT" ]; then
    echo "" >> "$PRE_COMMIT"
    echo "# detect-secrets pre-commit check (added by improvement-loop plugin)" >> "$PRE_COMMIT"
  else
    cat > "$PRE_COMMIT" << 'HOOK_HEADER'
#!/usr/bin/env bash
# Global pre-commit hook

# detect-secrets pre-commit check (added by improvement-loop plugin)
HOOK_HEADER
  fi

  cat >> "$PRE_COMMIT" << 'HOOK_BODY'
if command -v detect-secrets &> /dev/null; then
  # Get list of staged files
  STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)
  if [ -n "$STAGED_FILES" ]; then
    # Check for secrets in staged files
    if echo "$STAGED_FILES" | xargs detect-secrets scan --list-all-plugins 2>/dev/null | grep -q '"results": {}'; then
      : # No secrets found, continue
    else
      # Run the actual scan and check
      RESULTS=$(echo "$STAGED_FILES" | xargs detect-secrets scan 2>/dev/null)
      if echo "$RESULTS" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if not r.get('results') else 1)" 2>/dev/null; then
        : # Clean
      else
        echo "ERROR: detect-secrets found potential secrets in staged files:"
        echo "$RESULTS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for filepath, secrets in data.get('results', {}).items():
    for s in secrets:
        print(f'  {filepath}:{s[\"line_number\"]} - {s[\"type\"]}')
" 2>/dev/null
        echo ""
        echo "To allow a false positive, run: detect-secrets scan --update .secrets.baseline"
        echo "Then: git add .secrets.baseline"
        exit 1
      fi
    fi
  fi
fi
HOOK_BODY

  chmod +x "$PRE_COMMIT"
  echo "Pre-commit hook written to $PRE_COMMIT"
fi

# Configure git to use global hooks directory
git config --global core.hooksPath "$GLOBAL_HOOKS_DIR"
echo "Git configured to use global hooks at $GLOBAL_HOOKS_DIR"

# Create initial baseline for ~/.claude if it's a git repo
if [ -d "$HOME/.claude/.git" ]; then
  cd "$HOME/.claude"
  if [ ! -f .secrets.baseline ]; then
    detect-secrets scan > .secrets.baseline 2>/dev/null || true
    echo "Created .secrets.baseline in ~/.claude"
  fi
fi

echo "=== detect-secrets setup complete ==="
