#!/usr/bin/env python3
"""Register a finished batch into ledger (batches_index + journal + progress_latest)."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(p: Path, default):
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.home() / "projects" / "hh_work")
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--summary", default="", help="one-line journal summary")
    ap.add_argument("--progress", default="", help="one-line progress summary")
    args = ap.parse_args()

    root = args.root.expanduser().resolve()
    bdir = root / "batches" / args.batch_id
    if not bdir.is_dir():
        raise SystemExit(f"batch not found: {bdir}")

    ledger = root / "ledger"
    ledger.mkdir(parents=True, exist_ok=True)

    meta = load_json(bdir / "meta.json", {})
    metrics = load_json(bdir / "metrics.json", {})
    idx_path = ledger / "batches_index.json"
    index = load_json(idx_path, {"batches": []})

    entry = {
        "batch_id": args.batch_id,
        "path": f"batches/{args.batch_id}",
        "type": meta.get("type"),
        "created_at": meta.get("created_at"),
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "hands": metrics.get("hands", meta.get("hands")),
        "net_chip": metrics.get("net_chip"),
        "bb100_chip": metrics.get("bb100_chip"),
        "vpip": metrics.get("vpip"),
        "pfr": metrics.get("pfr"),
        "summary": args.summary,
    }
    # replace if re-finalizing same id
    index["batches"] = [b for b in index.get("batches", []) if b.get("batch_id") != args.batch_id]
    index["batches"].append(entry)
    index["batches"].sort(key=lambda b: b.get("created_at") or b.get("batch_id") or "")
    index["updated_at"] = datetime.now(timezone.utc).isoformat()
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    journal = ledger / "journal.md"
    if not journal.is_file():
        journal.write_text("# HH Analysis Journal\n\n", encoding="utf-8")
    block = (
        f"## {args.batch_id}\n\n"
        f"- registered: {entry['registered_at']}\n"
        f"- hands: {entry.get('hands')}\n"
        f"- net_chip: {entry.get('net_chip')}\n"
        f"- bb100_chip: {entry.get('bb100_chip')}\n"
        f"- vpip/pfr: {entry.get('vpip')}/{entry.get('pfr')}\n"
        f"- summary: {args.summary or '(see conclusions.md)'}\n"
        f"- progress: {args.progress or '(n/a — first batch or see conclusions)'}\n"
        f"- path: batches/{args.batch_id}/conclusions.md\n\n"
    )
    # append only if not already present
    existing = journal.read_text(encoding="utf-8")
    if f"## {args.batch_id}\n" not in existing:
        with journal.open("a", encoding="utf-8") as f:
            f.write(block)
    else:
        # still append a re-register note
        with journal.open("a", encoding="utf-8") as f:
            f.write(
                f"### re-finalize {args.batch_id} @ {entry['registered_at']}\n\n"
                f"- summary: {args.summary}\n"
                f"- progress: {args.progress}\n\n"
            )

    progress_path = ledger / "progress_latest.md"
    progress_path.write_text(
        f"# Progress latest\n\n"
        f"- batch: `{args.batch_id}`\n"
        f"- updated: {entry['registered_at']}\n"
        f"- hands: {entry.get('hands')}\n"
        f"- net_chip: {entry.get('net_chip')}\n"
        f"- bb100_chip: {entry.get('bb100_chip')} (high variance if small n)\n"
        f"- vpip/pfr: {entry.get('vpip')}/{entry.get('pfr')}\n\n"
        f"## One-liner\n\n{args.progress or args.summary or 'See conclusions.md'}\n\n"
        f"## Full write-up\n\n`batches/{args.batch_id}/conclusions.md`\n",
        encoding="utf-8",
    )
    print(f"updated {idx_path}")
    print(f"updated {journal}")
    print(f"updated {progress_path}")


if __name__ == "__main__":
    main()
