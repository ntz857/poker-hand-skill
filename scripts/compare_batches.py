#!/usr/bin/env python3
"""Diff two metrics.json files for progress reporting (structure first)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


KEYS = [
    "hands",
    "net_chip",
    "net_norake",
    "bb100_chip",
    "bb100_norake",
    "max_drawdown_chip",
    "vpip",
    "pfr",
    "vpip_pfr_gap",
    "three_bet",
    "saw_flop",
    "wtsd",
]


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", type=Path, help="previous metrics.json")
    ap.add_argument("current", type=Path, help="current metrics.json")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()
    a = load(args.baseline)
    b = load(args.current)
    diff = {"baseline_hands": a.get("hands"), "current_hands": b.get("hands"), "delta": {}}
    print(f"baseline hands={a.get('hands')}  current hands={b.get('hands')}")
    print(f"{'metric':20} {'base':>10} {'curr':>10} {'delta':>10}")
    for k in KEYS:
        av, bv = a.get(k), b.get(k)
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            d = bv - av
            diff["delta"][k] = round(d, 4) if isinstance(d, float) else d
            print(f"{k:20} {av!s:>10} {bv!s:>10} {d:+.2f}" if isinstance(d, float) else f"{k:20} {av!s:>10} {bv!s:>10} {d:+}")
        else:
            print(f"{k:20} {av!s:>10} {bv!s:>10}")
    # position overlap
    pa, pb = a.get("by_position") or {}, b.get("by_position") or {}
    print("\nby_position net_chip delta:")
    for pos in sorted(set(pa) | set(pb)):
        na = (pa.get(pos) or {}).get("net_chip", 0) or 0
        nb = (pb.get(pos) or {}).get("net_chip", 0) or 0
        print(f"  {pos:4} {na:+8.2f} -> {nb:+8.2f}  d={nb-na:+.2f}")
    print("\nNote: bb/100 deltas on small samples are high variance; prioritize structure.")
    if args.json_out:
        args.json_out.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()
