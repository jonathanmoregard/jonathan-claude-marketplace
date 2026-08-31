# Unified Proposals Folder

The plugin's SessionStart banner (`hooks/pending-proposals.py`), its UserPromptSubmit nudge (`hooks/pending-proposals-nudge.py`), and the `/review-improvements` skill all look at a single aggregation folder for pending work across multiple sources. All three count through one shared module, `hooks/proposal_counts.py`, so the number can never differ between surfaces.

## Default layout

The folder lives **outside** `~/.claude`. That directory is the live config repo the harness reads, and an unattended nightly reviewer writing proposals into it leaves it permanently dirty.

```
~/.local/state/claude-proposals/              # config.proposals.folder
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
    "folder": "~/.local/state/claude-proposals",
    "rsi_subdir": "rsi",
    "pending_statuses": ["pending", "open"],
    "excluded_files": ["README*", ".*"],
    "excluded_subdirs": [".*", "archived"]
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `folder` | `~/.local/state/claude-proposals` | Aggregation root. `~` is expanded. Resolve it from config, falling back to this literal — never by walking the `~/.claude` compatibility symlinks. |
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

Two read-only fallbacks, both live only until a pre-relocation install cuts over:

1. If the rsi subdir is absent from the resolved folder AND the legacy dir `~/.claude/recursive-self-improvement/proposals/` exists as a real directory, that dir is counted as the rsi bucket.
2. If the resolved folder does not exist at all AND `~/.claude/proposals/` does, the legacy folder is counted instead.

Neither is a path any *writer* may rely on. Writers resolve from config and write to the real location; the `~/.claude` names survive as a compatibility shim for readers only.

## How to add a new source

1. `mkdir ~/.local/state/claude-proposals/<new-source>`
2. Writer (script, MCP server, subagent, whatever) drops `*.md` files there.
3. Next SessionStart shows `<new-source> N` in the nudge.
4. `/review-improvements` walks it after rsi and before/after other categories alphabetically.

No plugin edit. No config change (unless the new source needs a non-default filename pattern excluded).

## Migration from the legacy `~/.claude` layout

Superseded. Both proposal roots used to live inside `~/.claude`, wired to each other by a `proposals/rsi` symlink, which meant every nightly reviewer run left the live config repo dirty. They now live in the state sink, and the two old names survive only as absolute symlinks pointing into it:

```
~/.claude/proposals                            -> ~/.local/state/claude-proposals
~/.claude/recursive-self-improvement/proposals -> ~/.local/state/claude-proposals/rsi
```

Those symlinks are for readers that still use the old names. Nothing should resolve the sink *through* them, and no writer should depend on them existing. Set `proposals.folder` in `config.json` and write to the resolved path.
