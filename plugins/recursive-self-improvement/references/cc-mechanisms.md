# Claude Code Mitigation Mechanisms

Catalog of primitives for proposing fixes. **Research options for any observation must span at least two mechanisms** — three variants of the same mechanism (e.g., three CLAUDE.md rules) is a failure mode.

## Friction ordering

User prefers auto-triggered mechanisms. Order research-brief options by friction, lowest first:

1. Hook (zero user action)
2. Auto-triggered skill (Claude self-invokes via `description` match)
3. SessionStart context injection (fires every session)
4. CLAUDE.md rule (loaded every session)
5. cron + headless Claude (scheduled, unattended)
6. MCP server (persistent external integration)
7. Plugin (bundle of the above)
8. Slash-command skill — **manual invocation is a last resort**; only propose when deterministic user-controlled triggering is explicitly desirable

## Observation-shape → mechanism mapping

| Observation pattern | Default mechanism |
|---|---|
| User told Claude the same instruction 2+ times across sessions | CLAUDE.md rule |
| User manually repeats a reasoning workflow (commit, review, sync) | Skill, auto-triggered via `description` |
| Claude produces a bad output shape that a regex can detect | Stop hook |
| Claude about to run a disallowed tool call | PreToolUse hook |
| Post-edit work always needed (lint, format, typecheck) | PostToolUse hook |
| Signal the user needs to see at the top of every session | SessionStart hook with `additionalContext` |
| Work that can run unattended on a schedule | cron + `claude -p` |
| External system used across sessions (GitHub, DB, Slack) | MCP server |
| Multi-file bundle of the above | Plugin |

If no row matches cleanly, prefer the higher row (less friction).

---

## Hook

Shell command auto-fires on a lifecycle event: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`.

- **Use when:** the fix is deterministic — block, transform, inject context, run a linter, count something
- **Don't use when:** the fix requires reasoning (use a skill instead)
- **Lives in:** `~/.claude/settings.json` under `hooks`
- **Example:** "Claude keeps telling user to run commands" → Stop hook regexes the final message and blocks/reminds

## Auto-triggered skill

Markdown prompt Claude invokes itself when the task matches the skill's `description`.

- **Use when:** a repeatable reasoning workflow — commit drafting, PR review, monthly summary, dotfiles sync
- **Don't use when:** no reasoning needed (hook instead) or trigger is unreliable (propose SessionStart reminder + skill together)
- **Auto-trigger lever:** the `description` frontmatter field — must describe the user-observable trigger shape, e.g., `"Use when the user asks to commit changes or says 'lets commit'"`
- **Lives in:** `~/.claude/skills/<name>/SKILL.md`

## SessionStart context injection

A `SessionStart` hook prints JSON; its `additionalContext` is prepended to the next session.

- **Use when:** persistent pending state the user wants surfaced every time — pending proposals, stale PRs, unread mail
- **Don't use when:** one-off notification — this runs every session forever

## CLAUDE.md rule

Auto-loaded every session.

- **Use when:** behavior correction the user has repeated 2+ times across sessions
- **Don't use when:** the fix is a workflow (skill), a block (hook), or project-specific (put it in project CLAUDE.md)
- **Threshold rule:** ≥2 repetitions of the same instruction across different sessions is a prime candidate. A single correction is not.

## cron + headless Claude

`claude -p "<prompt>" --allowedTools "..." --permission-mode bypassPermissions` scheduled by cron or systemd timer.

- **Use when:** the work is unattended, bounded, and repeatable on a clock
- **Constrain tools** with `--allowedTools` — never leave headless runs unscoped
- **Example:** the RSI daily-review agent itself

## MCP server

Exposes external tools to Claude via stdio.

- **Use when:** recurring integration with a system that has a stable API and appears across multiple sessions
- **Don't use when:** a one-off bash command suffices
- **Add with:** `claude mcp add <name> -- <command>`

## Plugin

Marketplace-distributable bundle of skills, hooks, agents, commands.

- **Use when:** multi-file mechanism that belongs together and might be reused elsewhere
- **Don't use when:** a single skill or hook — overhead not justified

## Slash-command skill (manual)

Same shape as an auto-triggered skill but invoked with `/<name>`.

- **Use when:** deterministic manual control is specifically desirable — rare
- **Default alternative:** give the skill a sharp `description` so Claude auto-invokes it. Propose the `/slash` form only if the user has asked for explicit invocation.

---

## Anti-patterns

- All three research options land on CLAUDE.md → not using this catalog
- Slash-command skill proposed as Option A → user prefers auto-trigger; move it to Option C or drop it
- Hook where judgment is needed → will misfire
- Skill where a regex hook suffices → extra latency and tokens
- New plugin proposed for a single file → overhead exceeds benefit
