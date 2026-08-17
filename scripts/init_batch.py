#!/usr/bin/env python3
"""Create a new analysis batch folder under hh_work/batches/."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def next_batch_id(batches_dir: Path, slug: str, day: str | None = None) -> str:
    day = day or datetime.now().strftime("%Y%m%d")
    slug = re.sub(r"[^\w\-]+", "_", slug).strip("_")[:40] or "batch"
    existing = []
    if batches_dir.is_dir():
        for p in batches_dir.iterdir():
            if p.is_dir() and p.name.startswith(day + "_"):
                m = re.match(rf"{day}_(\d{{3}})_", p.name)
                if m:
                    existing.append(int(m.group(1)))
    nnn = max(existing, default=0) + 1
    return f"{day}_{nnn:03d}_{slug}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.home() / "projects" / "hh_work")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--type", default="session", choices=["session", "theme", "full_rebuild", "legacy"])
    ap.add_argument(
        "--hand-ids-from-ingest",
        action="store_true",
        help="use raw/last_ingest.json new_hand_ids",
    )
    ap.add_argument("--hand-ids-file", type=Path, default=None)
    ap.add_argument("--all-raw", action="store_true", help="all hand_ids from index.jsonl")
    ap.add_argument("--day", default=None, help="YYYYMMDD override")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    root = args.root.expanduser().resolve()
    batches = root / "batches"
    batches.mkdir(parents=True, exist_ok=True)
    (root / "ledger").mkdir(parents=True, exist_ok=True)

    batch_id = next_batch_id(batches, args.slug, args.day)
    bdir = batches / batch_id
    bdir.mkdir(parents=True, exist_ok=False)

    hand_ids: list[str] = []
    if args.hand_ids_from_ingest:
        man = root / "raw" / "last_ingest.json"
        if man.is_file():
            hand_ids = json.loads(man.read_text(encoding="utf-8")).get("new_hand_ids", [])
    if args.hand_ids_file and args.hand_ids_file.is_file():
        text = args.hand_ids_file.read_text(encoding="utf-8")
        if args.hand_ids_file.suffix.lower() == ".json":
            data = json.loads(text)
            hand_ids = data if isinstance(data, list) else data.get("hand_ids", [])
        else:
            hand_ids = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if args.all_raw:
        index = root / "raw" / "hands" / "index.jsonl"
        hand_ids = []
        if index.is_file():
            for line in index.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    hand_ids.append(json.loads(line)["hand_id"])

    meta = {
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "type": args.type,
        "slug": args.slug,
        "stakes": "",
        "hands": len(hand_ids),
        "hands_new_to_raw": len(hand_ids) if args.hand_ids_from_ingest else None,
        "hands_duplicate": None,
        "datetime_min": "",
        "datetime_max": "",
        "parser": "parse_hh.py",
        "metrics_version": 1,
        "notes": args.notes,
    }
    (bdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (bdir / "hand_ids.json").write_text(
        json.dumps({"hand_ids": hand_ids, "count": len(hand_ids)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # stub conclusions
    (bdir / "conclusions.md").write_text(
        f"# {batch_id}\n\n_TODO: fill after analysis_\n",
        encoding="utf-8",
    )
    print(batch_id)
    print(str(bdir))


if __name__ == "__main__":
    main()
