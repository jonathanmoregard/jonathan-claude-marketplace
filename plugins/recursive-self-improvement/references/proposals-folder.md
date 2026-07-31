# Unified Proposals Folder

The plugin's SessionStart hook (`hooks/pending-proposals.py`) and `/review-improvements` skill both look at a single aggregation folder for pending work across multiple sources.

## Default layout

```
~/.claude/proposals/                          # config.proposals.folder
├── rsi/                                      # config.proposals.rsi_subdir  (status-aware)
├── router/                                   # any subdir  (file-existence based)
├── clv2/
├── from-research/
├── <any_new_subdir>/                         # auto-discovered
└── README.md                                 # excluded by filename pattern
```

**Drop a new subdir at the root, and the next SessionStart nudge picks it up automatically.** No plugin edit required.

## Config keys (all optional — defaults apply when absent)

Add a `proposals` section to `~/.claude/recursive-self-improvement/config/config.json`:

```json
{
  "proposals": {
    "folder": "~/.claude/proposals",
    "rsi_subdir": "rsi",
    "pending_statuses": ["pending", "open"],
    "excluded_files": ["README*", ".*"],
    "excluded_subdirs": [".*", "archived"]
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `folder` | `~/.claude/proposals` | Aggregation root. `~` is expanded. |
| `rsi_subdir` | `rsi` | Name of the subdir treated as status-aware (frontmatter-based). |
| `pending_statuses` | `["pending", "open"]` | For the rsi subdir, frontmatter status values counted as pending. Files with no `status:` line are also counted (permissive). |
| `excluded_files` | `["README*", ".*"]` | fnmatch globs — filenames matching any of these are skipped in every subdir. |
| `excluded_subdirs` | `[".*", "archived"]` | fnmatch globs — subdirs at the folder root matching any of these are skipped. |

## Counting semantics per category

- **rsi subdir** (frontmatter-driven, status-aware):
  - `status: pending` → counted
  - `status: open` → counted (backward-compat with pre-2026-05 proposals)
  - no `status:` line at all → counted (permissive fallback)
  - `status: implemented`, `status: rejected`, `status: deferred`, etc → not counted
- **Any other subdir** (file-existence-based):
  - Every `.md` file at the top level of the subdir counts, minus filename excludes.
  - Drain by moving the file to `<subdir>/archived/` (or `archived/rejected/`), or by deleting it.

## Backward compatibility

If the new folder / rsi subdir doesn't exist yet AND the legacy dir `~/.claude/recursive-self-improvement/proposals/` exists as a real directory, the hook counts the legacy dir as the rsi bucket. Pre-migration installs keep working.

## How to add a new source

1. `mkdir ~/.claude/proposals/<new-source>`
2. Writer (script, MCP server, subagent, whatever) drops `*.md` files there.
3. Next SessionStart shows `<new-source> N` in the nudge.
4. `/review-improvements` walks it after rsi and before/after other categories alphabetically.

No plugin edit. No config change (unless the new source needs a non-default filename pattern excluded).

## Migration from legacy layout

Two options:

**A. Symlink (default, zero-copy)** — the install script does this on fresh installs:
```
ln -sfn ~/.claude/recursive-self-improvement/proposals ~/.claude/proposals/rsi
```
Both paths point at the same files. Daily-review prompt keeps writing to the legacy path; hook and skill see them via the symlink.

**B. Move + reverse symlink** — one-time cutover if you want rsi files under `~/.claude/proposals/` for real:
```
mkdir -p ~/.claude/proposals/rsi
mv ~/.claude/recursive-self-improvement/proposals/*.md ~/.claude/proposals/rsi/
rmdir ~/.claude/recursive-self-improvement/proposals
ln -sfn ~/.claude/proposals/rsi ~/.claude/recursive-self-improvement/proposals
```
Reverses the symlink direction so the daily prompt still writes to `~/.claude/recursive-self-improvement/proposals/` (now a symlink into the aggregation folder).
