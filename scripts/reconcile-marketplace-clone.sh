#!/usr/bin/env bash
#
# reconcile-marketplace-clone.sh — retire a marketplace clone's local
# marketplace.json overlay once the same entry exists upstream, then
# fast-forward.
#
# Background. A checkout that serves plugins to the running Claude Code harness
# can carry a local wiring overlay: a `plugins/<name>` symlink into a working
# copy plus the matching `marketplace.json` entry registering it. The symlink is
# untracked and harmless; the manifest edit is a modification to a TRACKED file,
# and it is what makes `git pull --ff-only` refuse. The clone then rots and the
# harness serves stale content for every plugin in it.
#
# The fix is to carry the entry upstream and ignore the source path, so tracked
# content matches origin exactly. This script performs the one-time local
# reconciliation that lands after that change merges.
#
# It never runs `git stash` and never discards a local modification it cannot
# account for. If the working tree carries anything beyond the known overlay it
# aborts and prints the diff, leaving every byte where it was.
#
# Usage:
#   scripts/reconcile-marketplace-clone.sh [clone-path]
#   MARKETPLACE_CLONE=/path/to/clone scripts/reconcile-marketplace-clone.sh
#
# Idempotent: re-running after a successful reconcile fetches, finds nothing to
# do, and exits 0.
#
# Exit codes: 0 reconciled or already reconciled; 1 aborted, nothing changed.

set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENTRIES="$HERE/marketplace_entries.py"
[[ -f $ENTRIES ]] || { printf 'ABORT: cannot find %s\n' "$ENTRIES" >&2; exit 1; }

DEFAULT_CLONE="$HOME/.claude/plugins/marketplaces/jonathanmoregard"
CLONE="${1:-${MARKETPLACE_CLONE:-$DEFAULT_CLONE}}"
MANIFEST_REL=".claude-plugin/marketplace.json"
OVERLAY_PLUGIN="${OVERLAY_PLUGIN:-superpowers}"
OVERLAY_PATH_REL="plugins/$OVERLAY_PLUGIN"

say()  { printf '%s\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\nABORT: %s\n' "$*" >&2; exit 1; }

# --- 0. the clone is a git checkout with a remote --------------------------
[[ -d $CLONE ]] || die "no such directory: $CLONE"
git -C "$CLONE" rev-parse --git-dir >/dev/null 2>&1 \
  || die "not a git checkout: $CLONE"
git -C "$CLONE" remote get-url origin >/dev/null 2>&1 \
  || die "$CLONE has no 'origin' remote; nothing to fast-forward from"

BRANCH="$(git -C "$CLONE" symbolic-ref --quiet --short HEAD || true)"
[[ -n $BRANCH ]] || die "$CLONE has a detached HEAD; check out its branch first"
UPSTREAM="$(git -C "$CLONE" rev-parse --abbrev-ref --symbolic-full-name \
              "@{upstream}" 2>/dev/null || true)"
[[ -n $UPSTREAM ]] || die "branch '$BRANCH' has no upstream; set one before reconciling"

say "clone      : $CLONE"
say "branch     : $BRANCH -> $UPSTREAM"

# --- 1. record the pre-state we must preserve ------------------------------
# The symlink is the live-dev wiring. Capture its target now so we can prove
# it survived, and refuse to proceed if it is already broken.
LINK_BEFORE=""
if [[ -L $CLONE/$OVERLAY_PATH_REL ]]; then
  LINK_BEFORE="$(readlink "$CLONE/$OVERLAY_PATH_REL")"
  say "overlay    : $OVERLAY_PATH_REL -> $LINK_BEFORE"
  [[ -d $CLONE/$OVERLAY_PATH_REL ]] \
    || die "$OVERLAY_PATH_REL is a dangling symlink -> $LINK_BEFORE
       Fix the target before reconciling; this script must not paper over it."
elif [[ -e $CLONE/$OVERLAY_PATH_REL ]]; then
  say "overlay    : $OVERLAY_PATH_REL (a real path, not a symlink)"
else
  say "overlay    : $OVERLAY_PATH_REL absent"
fi

PLUGINS_BEFORE="$(python3 "$ENTRIES" \
                   --file "$CLONE/$MANIFEST_REL" 2>/dev/null || true)"

# --- 2. fetch, and require the entry to exist upstream ---------------------
say ""
say "fetching $UPSTREAM ..."
git -C "$CLONE" fetch --quiet origin

UPSTREAM_MANIFEST="$(git -C "$CLONE" show "$UPSTREAM:$MANIFEST_REL" 2>/dev/null || true)"
[[ -n $UPSTREAM_MANIFEST ]] \
  || die "$UPSTREAM has no $MANIFEST_REL — refusing to touch the working tree"

if ! printf '%s' "$UPSTREAM_MANIFEST" \
     | python3 "$ENTRIES" \
         --has-plugin "$OVERLAY_PLUGIN" >/dev/null; then
  die "$UPSTREAM does not yet carry a '$OVERLAY_PLUGIN' entry in $MANIFEST_REL.
       Reconciling now would drop the local entry and unregister the plugin.
       Merge the upstream change first, then re-run."
fi
info "$UPSTREAM carries the '$OVERLAY_PLUGIN' entry"

# --- 3. account for every local modification -------------------------------
# Tracked modifications: exactly one file may differ, and only in the one way
# we understand. Anything else is somebody's unfinished work.
DIRTY="$(git -C "$CLONE" status --porcelain=v1 --untracked-files=no)"
CHANGED_FILES="$(printf '%s\n' "$DIRTY" | sed -n 's/^.\{3\}//p' | sed '/^$/d')"

UNEXPECTED="$(printf '%s\n' "$CHANGED_FILES" | grep -v "^$MANIFEST_REL\$" || true)"
if [[ -n $UNEXPECTED ]]; then
  say ""
  say "Local modifications this script does not recognise:"
  printf '%s\n' "$UNEXPECTED" | sed 's/^/    /'
  say ""
  say "--- git diff ---"
  mapfile -t UNEXPECTED_PATHS <<< "$UNEXPECTED"
  git -C "$CLONE" --no-pager diff -- "${UNEXPECTED_PATHS[@]}" || true
  die "refusing to discard unrecognised local work. Nothing was changed.
       Commit, move aside, or revert these yourself, then re-run."
fi

NEEDS_RESTORE=0
if printf '%s\n' "$CHANGED_FILES" | grep -qx "$MANIFEST_REL"; then
  NEEDS_RESTORE=1
  HEAD_MANIFEST="$(git -C "$CLONE" show "HEAD:$MANIFEST_REL")"
  VERDICT="$(printf '%s' "$HEAD_MANIFEST" \
    | python3 "$ENTRIES" \
        --explain-overlay "$OVERLAY_PLUGIN" \
        --working "$CLONE/$MANIFEST_REL" \
        --upstream-json "$UPSTREAM_MANIFEST" || true)"
  if [[ $VERDICT != OK* ]]; then
    say ""
    say "The local $MANIFEST_REL edit is not just the '$OVERLAY_PLUGIN' entry:"
    printf '%s\n' "${VERDICT:-manifest comparison failed}" | sed 's/^/    /'
    say ""
    say "--- git diff -- $MANIFEST_REL ---"
    git -C "$CLONE" --no-pager diff -- "$MANIFEST_REL" || true
    die "refusing to discard an edit that carries more than the known overlay.
       Nothing was changed."
  fi
  info "local $MANIFEST_REL edit is exactly the '$OVERLAY_PLUGIN' entry,"
  info "and it is byte-equal to the entry now upstream — discarding loses nothing"
else
  info "no local $MANIFEST_REL edit (already reconciled)"
fi

# --- 4. pre-flight the fast-forward ----------------------------------------
# An untracked file at a path the incoming commits add would make `pull` fail
# AFTER we restored the manifest. Catch it while the tree is still untouched.
INCOMING="$(git -C "$CLONE" diff --name-only HEAD.."$UPSTREAM" || true)"
if [[ -n $INCOMING ]]; then
  COLLIDE=""
  while IFS= read -r p; do
    [[ -n $p ]] || continue
    if [[ -e $CLONE/$p || -L $CLONE/$p ]] \
       && ! git -C "$CLONE" ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
      COLLIDE+="$p"$'\n'
    fi
  done <<< "$INCOMING"
  if [[ -n $COLLIDE ]]; then
    say ""
    say "Untracked files sit where incoming commits add tracked files:"
    printf '%s' "$COLLIDE" | sed 's/^/    /'
    die "the fast-forward would overwrite them. Nothing was changed."
  fi
fi

# --- 5. restore, then fast-forward -----------------------------------------
if (( NEEDS_RESTORE )); then
  say ""
  say "restoring $MANIFEST_REL to the tracked version ..."
  git -C "$CLONE" checkout -- "$MANIFEST_REL"
fi

BEHIND="$(git -C "$CLONE" rev-list --count "HEAD..$UPSTREAM")"
say ""
if [[ $BEHIND == 0 ]]; then
  info "already at $UPSTREAM — nothing to fast-forward"
else
  say "fast-forwarding $BEHIND commit(s) ..."
  git -C "$CLONE" pull --ff-only
fi

# --- 6. prove the result ----------------------------------------------------
say ""
say "verifying:"

if [[ -n $LINK_BEFORE ]]; then
  [[ -L $CLONE/$OVERLAY_PATH_REL ]] \
    || die "$OVERLAY_PATH_REL is no longer a symlink — the fast-forward clobbered the overlay"
  LINK_AFTER="$(readlink "$CLONE/$OVERLAY_PATH_REL")"
  [[ $LINK_AFTER == "$LINK_BEFORE" ]] \
    || die "$OVERLAY_PATH_REL now points at $LINK_AFTER (was $LINK_BEFORE)"
  [[ -f $CLONE/$OVERLAY_PATH_REL/.claude-plugin/plugin.json ]] \
    || die "$OVERLAY_PATH_REL/.claude-plugin/plugin.json is not readable through the symlink"
  info "symlink intact: $OVERLAY_PATH_REL -> $LINK_AFTER (plugin.json readable)"
fi

python3 "$ENTRIES" \
  --compare-before "$PLUGINS_BEFORE" \
  --file "$CLONE/$MANIFEST_REL" \
  || die "the plugin set regressed across the fast-forward (see above)"

RESIDUE="$(git -C "$CLONE" status --porcelain=v1)"
if [[ -n $RESIDUE ]]; then
  say ""
  say "  working tree is NOT clean after reconciling:"
  printf '%s\n' "$RESIDUE" | sed 's/^/    /'
  die "the next 'git pull --ff-only' would refuse again. Investigate before
       relying on unattended updates."
fi
info "working tree clean — 'git pull --ff-only' will keep working"

say ""
say "reconciled."
