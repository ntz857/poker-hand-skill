#!/usr/bin/env python3
"""Build metrics.json (v1) from hero_hands.csv."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def truthy(v) -> bool:
    return str(v).lower() in ("1", "true", "yes")


def fnum(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def metrics_from_rows(rows: list[dict], bb_default: float = 0.5) -> dict:
    if not rows:
        return {
            "metrics_version": 1,
            "hands": 0,
            "net_chip": 0.0,
            "net_norake": 0.0,
            "bb": bb_default,
            "bb100_chip": 0.0,
            "bb100_norake": 0.0,
            "max_drawdown_chip": 0.0,
            "vpip": 0.0,
            "pfr": 0.0,
            "vpip_pfr_gap": 0.0,
            "three_bet": 0.0,
            "saw_flop": 0.0,
            "wtsd": 0.0,
            "by_position": {},
            "by_line": {},
            "big_loss_hand_ids": [],
            "big_win_hand_ids": [],
            "cumulative": None,
        }

    n = len(rows)
    bb = fnum(rows[0].get("bb"), bb_default) or bb_default
    net_chip = sum(fnum(r.get("net_chip")) for r in rows)
    net_norake = sum(fnum(r.get("net_norake")) for r in rows)

    # drawdown chronological if datetime present
    ordered = sorted(rows, key=lambda r: (r.get("datetime") or "", r.get("hand_id") or ""))
    peak = 0.0
    cur = 0.0
    max_dd = 0.0
    for r in ordered:
        cur += fnum(r.get("net_chip"))
        peak = max(peak, cur)
        max_dd = max(max_dd, peak - cur)

    vpip_n = sum(1 for r in rows if truthy(r.get("vpip")))
    pfr_n = sum(1 for r in rows if truthy(r.get("pfr")))
    three_n = sum(1 for r in rows if truthy(r.get("three_bet")))
    saw_n = sum(1 for r in rows if truthy(r.get("saw_flop")))
    wtsd_n = sum(1 for r in rows if truthy(r.get("went_to_showdown")))

    by_pos: dict[str, dict] = defaultdict(lambda: {"hands": 0, "net_chip": 0.0, "net_norake": 0.0, "vpip": 0, "pfr": 0})
    for r in rows:
        p = r.get("position") or "?"
        by_pos[p]["hands"] += 1
        by_pos[p]["net_chip"] += fnum(r.get("net_chip"))
        by_pos[p]["net_norake"] += fnum(r.get("net_norake"))
        by_pos[p]["vpip"] += 1 if truthy(r.get("vpip")) else 0
        by_pos[p]["pfr"] += 1 if truthy(r.get("pfr")) else 0

    by_pos_out = {}
    for p, d in by_pos.items():
        hn = d["hands"] or 1
        by_pos_out[p] = {
            "hands": d["hands"],
            "net_chip": round(d["net_chip"], 2),
            "net_norake": round(d["net_norake"], 2),
            "vpip": round(100 * d["vpip"] / hn, 2),
            "pfr": round(100 * d["pfr"] / hn, 2),
        }

    # line proxy from flags only (coarse)
    by_line = {
        "pfr_hands": {"n": pfr_n, "note": "approx open+3bet+iso via pfr flag"},
        "three_bet_hands": {"n": three_n},
        "vpip_not_pfr": {"n": max(0, vpip_n - pfr_n)},
    }

    losses = sorted(rows, key=lambda r: fnum(r.get("net_chip")))[:10]
    wins = sorted(rows, key=lambda r: -fnum(r.get("net_chip")))[:10]

    return {
        "metrics_version": 1,
        "hands": n,
        "net_chip": round(net_chip, 2),
        "net_norake": round(net_norake, 2),
        "bb": bb,
        "bb100_chip": round(net_chip / n / bb * 100, 2) if n else 0.0,
        "bb100_norake": round(net_norake / n / bb * 100, 2) if n else 0.0,
        "max_drawdown_chip": round(max_dd, 2),
        "vpip": round(100 * vpip_n / n, 2),
        "pfr": round(100 * pfr_n / n, 2),
        "vpip_pfr_gap": round(100 * (vpip_n - pfr_n) / n, 2),
        "three_bet": round(100 * three_n / n, 2),
        "saw_flop": round(100 * saw_n / n, 2),
        "wtsd": round(100 * wtsd_n / n, 2),
        "by_position": by_pos_out,
        "by_line": by_line,
        "big_loss_hand_ids": [
            {"hand_id": r.get("hand_id"), "net_chip": fnum(r.get("net_chip")), "cards": r.get("cards"), "position": r.get("position")}
            for r in losses
            if fnum(r.get("net_chip")) < 0
        ],
        "big_win_hand_ids": [
            {"hand_id": r.get("hand_id"), "net_chip": fnum(r.get("net_chip")), "cards": r.get("cards"), "position": r.get("position")}
            for r in wins
            if fnum(r.get("net_chip")) > 0
        ],
        "cumulative": None,
    }


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--cumulative-csv", type=Path, default=None, help="optional full-history CSV")
    args = ap.parse_args()
    rows = read_csv(args.csv_path)
    m = metrics_from_rows(rows)
    if args.cumulative_csv and args.cumulative_csv.is_file():
        m["cumulative"] = metrics_from_rows(read_csv(args.cumulative_csv))
        m["cumulative"]["cumulative"] = None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output} hands={m['hands']} net_chip={m['net_chip']:+.2f}")


if __name__ == "__main__":
    main()
