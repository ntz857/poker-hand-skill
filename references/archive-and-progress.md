# Archive & Progress Rules

Confirmed user config: **A1 B3 C2 D1 E3 F2 G1 H2**.

These rules are **mandatory** whenever analyzing hand histories for this user.

## Confirmed choices

| Code | Choice |
|------|--------|
| A1 | Data root: `~/projects/hh_work/` → Windows `C:\Users\bunny\projects\hh_work\` |
| B3 | Raw: `index.jsonl` + `by_id/<hand_id>.txt` + `by_month/YYYY-MM.txt` |
| C2 | Duplicates: skip if same hash; **warn and ask** if same `hand_id` but different `content_sha256` |
| D1 | Migrate legacy folder `0000019f` into structure as first batch |
| E3 | Each analysis: **new hands report** + **cumulative section** |
| F2 | Per-batch `conclusions.md` + append-only `ledger/journal.md` |
| G1 | Progress baseline: **previous batch** + **cumulative to previous** |
| H2 | Skill docs + helper scripts |

## Directory layout

```text
hh_work/
  raw/
    hands/
      index.jsonl                 # one JSON object per line (dedupe index)
      by_id/
        HD….txt                   # full hand text, one file per hand_id
      by_month/
        YYYY-MM.txt               # all hands that month, concatenated
    sources/
      <timestamp>_<original>      # untouched user uploads (zip/txt)
  batches/
    <batch_id>/
      meta.json
      hand_ids.json
      hero_hands.csv
      metrics.json
      conclusions.md
      notes_user.md               # optional
      opp_pl.csv                  # optional derived
  ledger/
    batches_index.json
    journal.md                    # append-only conclusion abstracts
    progress_latest.md            # latest progress summary (overwrite OK)
  legacy_backup/                  # optional old folders after migration
```

## Raw ingest (dedupe)

### Primary key

- `hand_id` (e.g. `HD2984404589`)

### On import

1. Copy original upload to `raw/sources/<UTC_timestamp>_<safe_name>`.
2. Split on `Poker Hand #` blocks.
3. For each hand:
   - Compute `content_sha256` of normalized hand text.
   - If `hand_id` **not** in index → write `by_id/`, append month file, append `index.jsonl`.
   - If `hand_id` **in** index and hash **equal** → count as `duplicate_same`.
   - If `hand_id` **in** index and hash **differs** → count as `duplicate_conflict`; **do not overwrite**; report to user and ask (C2).
4. Tell user: `new / duplicate_same / duplicate_conflict / parse_fail`.

### index.jsonl fields

```json
{
  "hand_id": "HD…",
  "datetime": "…",
  "table": "…",
  "stakes": "0.25/0.5",
  "site": "GG",
  "source_rel": "sources/…",
  "imported_at": "ISO-8601",
  "content_sha256": "…",
  "month": "YYYY-MM"
}
```

## Analysis batches

### batch_id

```text
YYYYMMDD_NNN_<slug>
```

Examples: `20260806_001_legacy_0000019f`, `20260808_002_new_session`.

### When to create a batch

| Trigger | batch type | hand_ids |
|---------|------------|----------|
| New HH + analyze | `session` | **new-to-raw** hands from this import (primary report) |
| Theme on existing raw | `theme` | filtered subset |
| Full recompute | `full_rebuild` | all raw hands |

Always also compute **cumulative metrics** over all raw hands known at batch time (E3). Store:

- Primary CSV/metrics for the batch hand set
- `metrics_cumulative.json` when batch is not already full history (or embed under `metrics.json` → `cumulative` key)

### Required files per batch

| File | Required |
|------|----------|
| `meta.json` | yes |
| `hand_ids.json` | yes |
| `hero_hands.csv` | yes |
| `metrics.json` | yes (`metrics_version`, core rates, dual EV) |
| `conclusions.md` | yes |
| `ledger` updates | yes (`batches_index.json`, `journal.md`, `progress_latest.md`) |

### meta.json (minimum)

```json
{
  "batch_id": "…",
  "created_at": "ISO-8601",
  "type": "session|theme|full_rebuild|legacy",
  "slug": "…",
  "stakes": "0.25/0.5",
  "hands": 0,
  "hands_new_to_raw": 0,
  "hands_duplicate": 0,
  "datetime_min": "…",
  "datetime_max": "…",
  "parser": "parse_hh.py",
  "metrics_version": 1,
  "notes": ""
}
```

### metrics.json core schema (`metrics_version: 1`)

```json
{
  "metrics_version": 1,
  "hands": 0,
  "net_chip": 0,
  "net_norake": 0,
  "bb": 0.5,
  "bb100_chip": 0,
  "bb100_norake": 0,
  "max_drawdown_chip": 0,
  "vpip": 0,
  "pfr": 0,
  "vpip_pfr_gap": 0,
  "three_bet": 0,
  "saw_flop": 0,
  "wtsd": 0,
  "by_position": {},
  "by_line": {},
  "big_loss_hand_ids": [],
  "big_win_hand_ids": [],
  "cumulative": null
}
```

Rates are **percent points** (e.g. `32.5` means 32.5%).  
`cumulative` is null for full_rebuild/legacy-all; otherwise same shape for all raw hands.

## conclusions.md template

Must include:

1. Scope (stakes, hands, new vs dup, time range, batch_id)
2. Dual EV + drawdown
3. Frequency structure
4. Position summary
5. Pool / opponents (if computed)
6. Structural findings (3–7 bullets)
7. Actionable rules (3–5) — carried to next batch review
8. Sample-size caveat
9. **vs 历史（进步/退步）** (G1) when any prior batch exists
10. Open questions / next focus

## Progress comparison (G1)

Baselines:

1. **Previous batch** (prefer same `type=session` if available, else last batch)
2. **Cumulative through previous batch** (from prior `metrics.json.cumulative` or recompute)

### Priority of judgment

1. Known leak frequencies (structure)
2. Line-type EV structure (open / 3bet / call_raise)
3. Recurrence of catastrophic line types
4. vs pool tags (LAG/reg/station) when tagged
5. bb/100 / profit — **reference only**, always variance-caveated

### Forbidden

- Calling level-up from a green session alone
- Calling level-down from 1–2 all-ins alone
- Cross-stakes bb/100 without disclosure

### Progress subsection format

```markdown
## vs 历史（进步 / 退步）

对比基线：batch A (N) → 本批 B (M)；累计至 A vs 累计至 B

### 进步
### 退步 / 未改善
### 仍不足以下定论
### 上批可执行规则复查
| 规则 | 本批是否遵守 | 证据 |
```

## journal.md (F2)

Append-only. Each batch adds:

```markdown
## <batch_id> — <date>

- hands: …
- net_chip: …
- one-line summary: …
- progress one-liner: …
- path: batches/<batch_id>/conclusions.md
```

## Agent mandatory workflow

1. Ingest → raw dedupe (`scripts/ingest_raw.py`)
2. Create batch dir + `meta.json` / `hand_ids.json`
3. Parse → `hero_hands.csv` + `metrics.json` (+ cumulative)
4. Standard strategy report (existing skill)
5. Load prior batches → progress section
6. Write `conclusions.md`
7. Update `ledger/batches_index.json`, append `journal.md`, write `progress_latest.md`
8. Chat summary + absolute paths to batch

**Analysis is incomplete if steps 6–7 are skipped.**

## Scripts

| Script | Role |
|--------|------|
| `scripts/ingest_raw.py` | Import zip/dir/txt → raw dedupe (B3, C2) |
| `scripts/metrics_from_csv.py` | CSV → metrics.json |
| `scripts/init_batch.py` | Create batch folder scaffold |
| `scripts/compare_batches.py` | Diff two metrics.json (structure) |
| `scripts/parse_hh.py` | Existing parser |

```bash
py -3 scripts/ingest_raw.py "C:\path\to\zip_or_dir" --root "C:\Users\bunny\projects\hh_work"
py -3 scripts/init_batch.py --root "C:\Users\bunny\projects\hh_work" --slug new_session --hand-ids-from-ingest last
py -3 scripts/parse_hh.py "C:\Users\bunny\projects\hh_work\raw\hands\by_id" --csv batches\...\hero_hands.csv
py -3 scripts/metrics_from_csv.py batches\...\hero_hands.csv -o batches\...\metrics.json
py -3 scripts/compare_batches.py batches\A\metrics.json batches\B\metrics.json
```

## Legacy migration (D1)

Folder `hh_work/0000019f` →:

1. Ingest all `.txt` into `raw/`
2. Batch `YYYYMMDD_001_legacy_0000019f` with existing CSV if present
3. Write conclusions from known session review
4. Move or copy original folder to `legacy_backup/0000019f` (keep readable backup)

## Sample honesty (unchanged)

- &lt;1000 hands: do not crown winner/loser on bb/100
- Structure + repeated line types &gt; single-session profit
