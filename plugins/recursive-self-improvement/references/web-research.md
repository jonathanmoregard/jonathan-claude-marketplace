# Web Research Routing

## The dead-grant problem

Granting a tool in `--allowedTools` (or a subagent tool list) does not make it available: a global deny in `~/.claude/settings.json` beats any per-agent grant. Empirically verified 2026-08-01 on a host where `WebSearch` and `WebFetch` are globally denied — an agent launched with `--allowedTools "... WebSearch WebFetch ..."` still has no web access. Its web tool calls are denied at runtime and the research step quietly degrades to whatever local context provides.

Two places in this plugin currently grant these tools. Both are owned by other in-flight changes and tracked as follow-ups — do not treat their grants as evidence the tools work:

- `scripts/install.sh` — the auto-research cron line: `--allowedTools "Read Glob Grep WebSearch WebFetch Write(...)"`
- `skills/review-improvements/SKILL.md` — the Human-Track subagent tool list: `Read Glob Grep WebSearch WebFetch`

## What to use instead

Where a prompt or skill in this plugin intends web research, route it through `mcp__research-agent__research(prompt, depth, model?)` when the host provides it:

- Runs in an isolated container, scans retrieved content for prompt injection, and returns a citation-ready report. For content fetched through it, this subsumes the LLM Guard recommendation from setup.
- `depth` costs real wall time — `fast` (~2–5 s, one-shot look-up), `normal` (~1.5–3 min, multi-source, default), `deep` (~3–6 min, broad fan-out). Unattended agents should default to `normal`.
- Grant it explicitly in the agent's tool list. MCP tools obey the same deny-beats-grant rule, so confirm it is not denied either.

## Host-dependence

On a host with no global deny and no research-agent MCP, the direct `WebSearch`/`WebFetch` grants work as originally designed. Do not assume either setup: check the deny lists in `~/.claude/settings.json` before relying on a web-capable agent, and prefer the research-agent path whenever it exists.
