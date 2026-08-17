# poker-hand-history (agent skill)

Agent skill for ingesting GG/PokerStars-style hand histories, dual-EV metrics, batch archive workflow, and exploit-first review.

## Layout

- `SKILL.md` — skill instructions for agents
- `scripts/` — `ingest_raw.py`, `parse_hh.py`, `init_batch.py`, `metrics_from_csv.py`, `finalize_batch.py`, …
- `references/` — archive rules, GG notes

## Data

This repo is **skill code only**. Personal archives should live in a **private** data repo (e.g. `poker-hands` / local `~/projects/hh_work`).

Dashboard UI: separate repo `poker-dashboard`.

## Quick use

```powershell
$skill = "$env:USERPROFILE\.agents\skills\poker-hand-history\scripts"
$root  = "$env:USERPROFILE\projects\hh_work"
py -3 "$skill\ingest_raw.py" "D:\path\to\export.zip" --root $root
```
