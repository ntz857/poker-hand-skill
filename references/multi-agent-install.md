# Multi-agent install

Canonical skill root:

```text
~/.agents/skills/poker-hand-history/
├── SKILL.md
├── scripts/parse_hh.py
└── references/
```

Uses the open [Agent Skills](https://agentskills.io/specification) layout (`SKILL.md` + YAML frontmatter). Compatible with any client that loads skills from a directory of folders containing `SKILL.md`.

## Preferred: one canonical copy + links

### Windows (PowerShell, junctions)

```powershell
$src = "$env:USERPROFILE\.agents\skills\poker-hand-history"

# Claude Code
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills" | Out-Null
cmd /c mklink /J "$env:USERPROFILE\.claude\skills\poker-hand-history" $src

# Grok
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.grok\skills" | Out-Null
cmd /c mklink /J "$env:USERPROFILE\.grok\skills\poker-hand-history" $src

# Codex (if using ~/.codex/skills)
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills" | Out-Null
cmd /c mklink /J "$env:USERPROFILE\.codex\skills\poker-hand-history" $src
```

### macOS / Linux

```bash
SRC="$HOME/.agents/skills/poker-hand-history"
mkdir -p ~/.claude/skills ~/.grok/skills ~/.codex/skills
ln -sfn "$SRC" ~/.claude/skills/poker-hand-history
ln -sfn "$SRC" ~/.grok/skills/poker-hand-history
ln -sfn "$SRC" ~/.codex/skills/poker-hand-history
```

## Per-agent notes

| Agent | Discovery | Notes |
|-------|-----------|--------|
| **Claude Code** | `~/.claude/skills/<name>/SKILL.md` | Auto-loads by description; also project `.claude/skills/` |
| **Grok** | `~/.grok/skills/<name>/SKILL.md` | Slash `/poker-hand-history` after reload |
| **Codex** | `~/.codex/skills/` or repo `.agents/skills/` | Confirm skills enabled in Codex settings |
| **OpenClaw** | Product skills path (often `~/.openclaw/skills` or configured root) | Symlink canonical folder; keep `SKILL.md` name |
| **Hermes** | Skills / tools directory per install docs | Same Agent Skills folder shape |
| **Cursor / other** | Project `.agents/skills` or rules that `@` the SKILL.md | Can `@~/.agents/skills/poker-hand-history/SKILL.md` |

## Project-scoped share

```bash
mkdir -p .agents/skills
cp -R ~/.agents/skills/poker-hand-history .agents/skills/
# or symlink
```

Commit `.agents/skills/poker-hand-history` if the team should share the workflow.

## Smoke test

```bash
py -3 ~/.agents/skills/poker-hand-history/scripts/parse_hh.py /path/to/hh_dir
# expect dual EV lines + position table
```

If another agent cannot find the skill, paste or `@` the absolute path to `SKILL.md` in the session.
