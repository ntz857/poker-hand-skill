---
name: poker-hand-history
description: >
  Use when the user provides poker hand histories (GGPoker/PokerStars-style .txt or .zip),
  asks for session/stats analysis, winrate, VPIP/PFR, position breakdown, exploit review,
  hand review, BTN leaks, opponent pool reads, or compares agent numbers to client HUD/stats UI.
  Also use for /poker-hand-history, /hh-review, "分析手牌", "牌谱", "复盘".
---

# Poker Hand History Analysis

## Overview

Parse cash-game hand histories into **chip-accurate EV**, dual **with-rake / without-rake** metrics, opponent pool tags, then review **exploitative** lines (not pure GTO). Validate against platform UI before coaching.

**Core principle:** Numbers first (verified), then people (pool), then lines (big pots / structural leaks). Never treat short-sample BB/100 as long-run truth.

**Archive principle (this user):** Raw hands are **deduped once** under `hh_work/raw/`; every analysis is a **batch** with CSV + `metrics.json` + `conclusions.md`; every new analysis must record **progress vs history**. Chat-only conclusions are incomplete. Full rules: `references/archive-and-progress.md` (config A1 B3 C2 D1 E3 F2 G1 H2).

## Multi-agent install

Canonical path (this skill):

```text
~/.agents/skills/poker-hand-history/
```

Wire the same folder into each agent (symlink/junction preferred so one copy stays canonical):

| Agent | Skills root | Action |
|-------|-------------|--------|
| **Claude Code** | `~/.claude/skills/` | Junction/symlink `poker-hand-history` → canonical |
| **Grok** | `~/.grok/skills/` | Same |
| **Codex** | `~/.codex/skills/` or project `.agents/skills/` | Copy or symlink; ensure Codex skills discovery is enabled |
| **OpenClaw / Hermes / others** | Agent Skills dir per product docs | Point at `~/.agents/skills/poker-hand-history` or copy tree |
| **Project-only** | `<repo>/.agents/skills/` or `<repo>/.claude/skills/` | Copy/symlink into repo for team share |

Windows junction example:

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\poker-hand-history" `
  -Target "$env:USERPROFILE\.agents\skills\poker-hand-history" -Force
New-Item -ItemType Junction -Path "$env:USERPROFILE\.grok\skills\poker-hand-history" `
  -Target "$env:USERPROFILE\.agents\skills\poker-hand-history" -Force
```

Portable parser (stdlib Python 3.10+):

```bash
python ~/.agents/skills/poker-hand-history/scripts/parse_hh.py /path/to/hh_dir_or_zip
python ~/.agents/skills/poker-hand-history/scripts/parse_hh.py /path/to/hh --csv out.csv
```

On Windows use `py -3` if `python` is missing.

## Workflow (always in this order)

### 0) Archive layout (mandatory for this user)

Data root (A1): `C:\Users\bunny\projects\hh_work\` (or `~/projects/hh_work/`).

```text
hh_work/raw/hands/{index.jsonl,by_id/,by_month/}   # deduped raw (B3)
hh_work/raw/sources/                               # original uploads
hh_work/batches/<batch_id>/                        # one folder per analysis
hh_work/ledger/{batches_index.json,journal.md,progress_latest.md}
```

**Never** only print results in chat. Each analysis creates a batch and updates the ledger.

### 1) Ingest (dedupe into raw)

1. Accept `.zip` / folder / `.txt` hand histories.
2. Run `scripts/ingest_raw.py <path> --root <hh_work>` (or equivalent):
   - Copy upload → `raw/sources/`
   - Split `Poker Hand #` blocks; key = `hand_id`
   - New id → write `by_id/` + append `by_month/` + `index.jsonl`
   - Same id + same hash → `duplicate_same` (skip)
   - Same id + **different hash** → `duplicate_conflict` (**do not overwrite**; warn and ask — C2)
3. Report counts: new / duplicate_same / duplicate_conflict / fail.
4. Detect site format (GGPoker `Dealt to Hero`, Jackpot, insurance; PokerStars-like seats).
5. If format unknown: sample 2–3 hands, map fields, then parse.

### 2) Parse correctly (chip EV)

Per hand, compute **Hero cash flows**:

| Item | Rule |
|------|------|
| Posts | SB/BB/**missed blind**/ante — all are real cost |
| `raises $X to $Y` | Add **`Y − already_committed_this_street`**, not raw `$X` |
| calls / bets | Add stated amount |
| Uncalled return | Credit to Hero |
| `Hero collected $` | Credit to Hero |
| **Insurance premium** | `Pays All-in Insurance premium ($…)` — **must subtract** |
| Insurance payout | Credit if present |

```text
net_chip = collected + returned + insurance_payout − put_in − insurance_premium
```

**Positions (6-max):** from button clockwise → SB, BB, then UTG…BTN. Short-handed tables drop middle labels (see script).

**Do not** use multiline `^([^:]+):` action regex — it swallows "Dealt to" lines and breaks VPIP.

### 3) Dual EV (required in every report)

| Metric | Definition | Use |
|--------|------------|-----|
| **含 Rake / `net_chip`** | Real stack change (pot already after rake) | Bankroll, drawdown, truth |
| **不含 Rake / `net_norake`** | `net_chip + rake_share` | Play-quality EV vs fee structure |

`rake_share`: if Hero collected,  
`rake × (hero_collected / sum_all_collected_from_pot)`; else `0` (splits get proportional share).

Always report **both**. Never present only one as "the" profit.

### 4) Reconcile before coaching

1. **Stack walk:** next hand Hero start stack ≈ prev start + `net_chip` (allow rebuy jumps to 50/100).
2. **Platform UI:**  
   - 翻牌% / Flop seen = **saw flop**, **not** VPIP  
   - 摊牌% should match WTSD  
   - Position 摊牌 counts should match  
   - Absolute 输赢 may differ if client is pre-rake / different fee attribution — explain; prefer stack-verified `net_chip`
3. Fix parser bugs before lecturing the user on strategy.

### 5) Aggregate stats + batch files

Always compute:

- Hands, `net_chip`, `net_norake`, BB/100 both, max drawdown (chip)
- VPIP, **saw flop**, PFR, VPIP−PFR gap, 3bet, fold-to-raise / call-raise when faced
- WTSD, W$SD
- By position, session/file, day
- Top wins/losses with board + street

**Batch (required):**

1. `scripts/init_batch.py` → `batches/YYYYMMDD_NNN_<slug>/`
2. Parse batch hands → `hero_hands.csv` (dual nets + flags)
3. `scripts/metrics_from_csv.py` → `metrics.json` (`metrics_version: 1`)
4. **E3:** primary scope = this batch’s hands (usually **new-to-raw**); also compute **cumulative** over all raw hands → `metrics.json.cumulative` or `metrics_cumulative.json`

Batch types: `session` | `theme` | `full_rebuild` | `legacy`.

### 6) Opponent pool (exploit layer)

For each non-Hero with enough hands at table (e.g. ≥15):

- VPIP, PFR, 3bet, fold-to-raise, WTSD, shown hands

Tag buckets:

| Tag | Rough signal | Default exploit |
|-----|--------------|-----------------|
| Station | High VPIP, very low PFR | Value thin; **never multi-street air** |
| Whale / maniac | VPIP 50%+ | Wide value; wider medium-hand calls; fewer fancy lines |
| LAG | High VPIP+PFR | Clear 3bet plan; fewer dominated flats |
| Nit | Very low VPIP | Respect raises / XR; less hero-call |

Small samples: tag as **hypothesis**, not gospel.

### 7) Strategy review (exploit-first)

**Frame:** Exploit primary; GTO as guardrail against −EV suicide lines.

**Prioritize hands:**

1. `|net_chip| ≥ ~3–6 BB`
2. Showdowns / all-ins / insurance
3. Multi-street pots
4. Structural position leaks (e.g. only red seat)

**For each major error, state:**

- Spot (position, cards, board, line)
- Opponent tag used (or "unknown")
- Why line fails **vs that player type**
- Better exploit line
- Whether result was run-good/run-bad (result ≠ correct)

**Accept user reads:** If user says "I only called because maniac", evaluate flop separately from preflop; don't auto-label every wide call as spew.

**Sample size honesty:**

| Question | Small n (e.g. 60 seats / 350 total) |
|----------|-------------------------------------|
| Long-run BB/100 | **Not reliable** |
| Frequency structure (VPIP vs PFR, flat vs open) | **Often enough** |
| Single catastrophic line | Logic stands even at n=1 |

### 8) Position deep-dive (when requested)

1. All hands at that seat; line-type breakdown (open / cold-call / call-3bet / 4bet…).
2. Separate **open pots** vs **passive entry**.
3. Rules: frequency leaks first; then big pots.
4. Output short enforceable rules, not a novel.

### 9) Progress vs history (G1 — required when prior batches exist)

Baselines: **previous batch** + **cumulative through previous**.

Judge in this order (structure before results):

1. Known leak frequencies  
2. Line-type EV (open / 3bet / call_raise)  
3. Whether catastrophic line types recur  
4. vs pool tags when available  
5. bb/100 / profit — reference only + variance caveat  

Do **not** crown improvement from a green session alone, or regression from 1–2 all-ins alone.

Optional helper: `scripts/compare_batches.py metrics_a.json metrics_b.json`.

### 10) Record conclusions + ledger (required)

Write `batches/<id>/conclusions.md` using the template in `references/archive-and-progress.md` (scope, dual EV, rates, findings, 3–5 rules, progress section, next focus).

Then:

1. Update `ledger/batches_index.json`
2. **Append** `ledger/journal.md` (F2 — never rewrite history)
3. Overwrite `ledger/progress_latest.md` with the latest progress summary

**Incomplete if conclusions/ledger are missing.**

## Red flags (stop and fix data)

- Platform 翻牌% matched to VPIP → wrong metric
- Raise accounting uses only `$X` in `raises $X to $Y` → overstated profit
- Ignoring insurance / missed blind → chip net too high
- Coaching winrate on &lt;1k hands as "you are a winner/loser" → overclaim
- Pure GTO critique on station-heavy tables without pool tags → wrong frame
- Blaming a good exploit call only because it lost (or praising spew only because it won)

## Output shape (default report)

1. Scope (stakes, hands, files, **batch_id**, new vs duplicate)  
2. Dual EV summary + drawdown (**batch** + **cumulative** if E3)  
3. Core rates (VPIP **and** saw flop)  
4. Position table (both nets)  
5. Reconcile note vs platform if user provided UI  
6. Pool tags (short)  
7. Major errors / good exploits (bullet list with hands)  
8. 3–5 actionable rules  
9. **vs 历史：进步 / 退步** (if prior batches)  
10. Sample-size caveat  
11. Paths: `batches/…/conclusions.md`, ledger files  

## Scripts

| Script | Role |
|--------|------|
| `scripts/ingest_raw.py` | Zip/dir/txt → deduped `raw/` (B3, C2) |
| `scripts/init_batch.py` | Create `batches/<id>/` scaffold + index stub |
| `scripts/parse_hh.py` | Parse HH → stats + optional CSV |
| `scripts/metrics_from_csv.py` | `hero_hands.csv` → `metrics.json` |
| `scripts/compare_batches.py` | Diff two `metrics.json` for progress |
| `scripts/finalize_batch.py` | Register batch in ledger + journal stub |

```bash
py -3 scripts/ingest_raw.py "C:\path\to\hh_or_zip" --root "C:\Users\bunny\projects\hh_work"
py -3 scripts/init_batch.py --root "C:\Users\bunny\projects\hh_work" --slug new_session
py -3 scripts/parse_hh.py "<hands_dir_or_list>" --csv "…/hero_hands.csv"
py -3 scripts/metrics_from_csv.py "…/hero_hands.csv" -o "…/metrics.json"
py -3 scripts/compare_batches.py "…/prev/metrics.json" "…/curr/metrics.json"
py -3 scripts/finalize_batch.py --root "C:\Users\bunny\projects\hh_work" --batch-id YYYYMMDD_NNN_slug
```

## References

- `references/archive-and-progress.md` — **archive, batch, conclusions, progress rules**  
- `references/ggpoker-notes.md` — GG-specific line formats and fee fields  
- `references/multi-agent-install.md` — install matrix detail  

## Common mistakes (agent)

| Mistake | Fix |
|---------|-----|
| One profit number | Always dual EV |
| Trust UI over stack walk | Prefer stack-verified chip |
| Review every fold | Focus big pots + structure |
| GTO-only tone on fish tables | Tag pool, exploit first |
| Ship unvalidated parser | Reconcile first |
| Chat-only analysis, no batch | Write `batches/…` + ledger (archive rules) |
| Overwrite raw on hash conflict | C2: warn and ask, never silent overwrite |
| Judge skill by one session bb/100 | Structure + progress section first |
