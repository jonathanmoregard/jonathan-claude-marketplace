#!/usr/bin/env bash
set -euo pipefail
cd ~/.claude
git add improvements/
if git diff --cached --quiet improvements/; then
  echo "No proposal changes to commit"
  exit 0
fi
git commit -m "improvement proposals: $(date +%Y-%m-%d)"
git push
