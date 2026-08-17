#!/usr/bin/env python3
"""Ingest HH zip/dir/txt into hh_work/raw with hand_id dedupe (B3, C2)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HAND_SPLIT = re.compile(r"(?=Poker Hand #)")
HAND_ID_RE = re.compile(r"Poker Hand #(HD\d+|\S+):")
DT_RE = re.compile(
    r"Poker Hand #\S+:.*?- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
)
TABLE_RE = re.compile(r"Table '([^']+)'")
STAKES_RE = re.compile(r"\(\$?([\d.]+)/\$?([\d.]+)\)")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_name(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", name)[:120]


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def load_index(index_path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not index_path.is_file():
        return out
    for line in index_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        out[obj["hand_id"]] = obj
    return out


def extract_sources(src: Path, staging: Path) -> list[Path]:
    staging.mkdir(parents=True, exist_ok=True)
    if src.is_file() and src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(staging)
        return sorted(staging.rglob("*.txt"))
    if src.is_file() and src.suffix.lower() == ".txt":
        dest = staging / src.name
        shutil.copy2(src, dest)
        return [dest]
    if src.is_dir():
        return sorted(src.rglob("*.txt"))
    raise SystemExit(f"Unsupported source: {src}")


def parse_hand_meta(hand_text: str) -> dict:
    hid_m = HAND_ID_RE.search(hand_text)
    if not hid_m:
        return {}
    hand_id = hid_m.group(1)
    dt_m = DT_RE.search(hand_text)
    table_m = TABLE_RE.search(hand_text)
    st_m = STAKES_RE.search(hand_text)
    datetime_s = dt_m.group(1) if dt_m else ""
    month = ""
    if datetime_s:
        # 2026/08/02 -> 2026-08
        month = datetime_s[0:4] + "-" + datetime_s[5:7]
    stakes = ""
    if st_m:
        stakes = f"{st_m.group(1)}/{st_m.group(2)}"
    site = "GG" if hand_id.startswith("HD") else "unknown"
    return {
        "hand_id": hand_id,
        "datetime": datetime_s,
        "table": table_m.group(1) if table_m else "",
        "stakes": stakes,
        "site": site,
        "month": month,
    }


def normalize_hand(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def append_month_file(month_path: Path, hand_text: str) -> None:
    month_path.parent.mkdir(parents=True, exist_ok=True)
    with month_path.open("a", encoding="utf-8") as f:
        if month_path.exists() and month_path.stat().st_size > 0:
            f.write("\n")
        f.write(hand_text if hand_text.endswith("\n") else hand_text + "\n")


def ingest(src: Path, root: Path) -> dict:
    raw = root / "raw"
    hands_dir = raw / "hands"
    by_id = hands_dir / "by_id"
    by_month = hands_dir / "by_month"
    sources = raw / "sources"
    index_path = hands_dir / "index.jsonl"
    for p in (by_id, by_month, sources):
        p.mkdir(parents=True, exist_ok=True)

    stamp = utc_stamp()
    src_dest = sources / f"{stamp}_{safe_name(src.name)}"
    if src.is_file():
        shutil.copy2(src, src_dest)
    else:
        # copy tree as zip-like folder
        if src_dest.exists():
            shutil.rmtree(src_dest)
        shutil.copytree(src, src_dest)

    staging = root / ".staging" / stamp
    if staging.exists():
        shutil.rmtree(staging)
    try:
        txts = extract_sources(src if src.is_dir() else src_dest, staging)
    except SystemExit:
        raise
    except Exception:
        # if we copied file to sources, extract from sources copy
        txts = extract_sources(src_dest if src_dest.is_file() else src, staging)

    index = load_index(index_path)
    stats = {
        "new": 0,
        "duplicate_same": 0,
        "duplicate_conflict": 0,
        "parse_fail": 0,
        "files": len(txts),
    }
    new_ids: list[str] = []
    conflicts: list[dict] = []

    source_rel = str(src_dest.relative_to(root)).replace("\\", "/")

    for tp in txts:
        text = tp.read_text(encoding="utf-8", errors="replace")
        chunks = HAND_SPLIT.split(text)
        for chunk in chunks:
            if "Poker Hand #" not in chunk:
                continue
            hand = normalize_hand(chunk)
            meta = parse_hand_meta(hand)
            if not meta.get("hand_id"):
                stats["parse_fail"] += 1
                continue
            hid = meta["hand_id"]
            digest = sha256_text(hand)
            if hid in index:
                old = index[hid].get("content_sha256", "")
                if old == digest:
                    stats["duplicate_same"] += 1
                else:
                    stats["duplicate_conflict"] += 1
                    conflicts.append(
                        {
                            "hand_id": hid,
                            "old_sha256": old,
                            "new_sha256": digest,
                            "source": source_rel,
                        }
                    )
                continue

            # new
            out_file = by_id / f"{hid}.txt"
            out_file.write_text(hand, encoding="utf-8")
            month = meta.get("month") or "unknown"
            append_month_file(by_month / f"{month}.txt", hand)
            rec = {
                **meta,
                "source_rel": source_rel,
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "content_sha256": digest,
            }
            with index_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            index[hid] = rec
            new_ids.append(hid)
            stats["new"] += 1

    # write last ingest manifest for init_batch
    manifest = {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "source": str(src),
        "source_rel": source_rel,
        "stats": stats,
        "new_hand_ids": new_ids,
        "conflicts": conflicts,
    }
    man_path = raw / "last_ingest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest HH into hh_work/raw (dedupe)")
    ap.add_argument("source", type=Path, help="zip, txt, or directory")
    ap.add_argument(
        "--root",
        type=Path,
        default=Path.home() / "projects" / "hh_work",
        help="hh_work root",
    )
    args = ap.parse_args()
    src = args.source.expanduser().resolve()
    root = args.root.expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"Source not found: {src}")
    root.mkdir(parents=True, exist_ok=True)
    man = ingest(src, root)
    s = man["stats"]
    print(f"root: {root}")
    print(
        f"new={s['new']}  duplicate_same={s['duplicate_same']}  "
        f"duplicate_conflict={s['duplicate_conflict']}  parse_fail={s['parse_fail']}  "
        f"txt_files={s['files']}"
    )
    if man["conflicts"]:
        print("CONFLICTS (same hand_id, different content) — not overwritten (C2):")
        for c in man["conflicts"][:20]:
            print(f"  {c['hand_id']} old={c['old_sha256'][:12]}… new={c['new_sha256'][:12]}…")
        print("Ask user before force-updating any conflicted hands.")
    print(f"manifest: {root / 'raw' / 'last_ingest.json'}")
    if man["new_hand_ids"]:
        print(f"new_hand_ids: {len(man['new_hand_ids'])} (first 5: {man['new_hand_ids'][:5]})")


if __name__ == "__main__":
    main()
