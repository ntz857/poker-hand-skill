#!/usr/bin/env python3
"""
Portable GGPoker / PokerStars-like cash HH parser (stdlib only).

Usage:
  python parse_hh.py <dir_or_zip> [--csv out.csv] [--json-summary]

Outputs dual EV:
  net_chip   — real stack change (with rake already in collected amounts;
               includes insurance premium & missed blind costs)
  net_norake — net_chip + hero rake_share
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Optional

RANK_ORDER = "23456789TJQKA"
POSITION_ORDER = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]


def parse_money(s: str) -> float:
    return float(s.replace("$", "").replace(",", ""))


def normalize_rank(r: str) -> str:
    r = r.upper()
    return "T" if r == "10" else r


def hand_category(cards: str) -> str:
    m = re.match(
        r"([2-9TJQKA]|10)([cdhs])\s+([2-9TJQKA]|10)([cdhs])", cards, re.I
    )
    if not m:
        return cards
    r1, s1, r2, s2 = m.groups()
    r1, r2 = normalize_rank(r1), normalize_rank(r2)
    suited = s1.lower() == s2.lower()
    i1, i2 = RANK_ORDER.index(r1), RANK_ORDER.index(r2)
    if i1 == i2:
        return f"{r1}{r2}"
    hi, lo = (r1, r2) if i1 > i2 else (r2, r1)
    return f"{hi}{lo}{'s' if suited else 'o'}"


def seat_positions(seats: list[int], button_seat: int) -> dict[int, str]:
    if not seats:
        return {}
    ordered = sorted(seats)
    try:
        btn_idx = ordered.index(button_seat)
    except ValueError:
        return {s: f"S{s}" for s in seats}
    n = len(ordered)
    circle = [ordered[(btn_idx + 1 + i) % n] for i in range(n)]
    labels_by_count = {
        2: ["SB", "BB"],
        3: ["SB", "BB", "BTN"],
        4: ["SB", "BB", "CO", "BTN"],
        5: ["SB", "BB", "UTG", "CO", "BTN"],
        6: ["SB", "BB", "UTG", "HJ", "CO", "BTN"],
    }
    labels = labels_by_count.get(n)
    if not labels:
        labels = [f"P{i}" for i in range(n)]
        labels[0], labels[1], labels[-1] = "SB", "BB", "BTN"
    return {circle[i]: labels[i] for i in range(n)}


@dataclass
class HandResult:
    hand_id: str
    datetime: str
    table: str
    file: str
    position: str
    cards: str
    category: str
    players: int
    net_chip: float
    net_norake: float
    rake: float
    rake_share: float
    insurance: float
    jackpot: float
    pot: float
    vpip: bool
    pfr: bool
    three_bet: bool
    faced_raise: bool
    fold_to_raise: bool
    called_raise: bool
    went_to_showdown: bool
    won_at_showdown: bool
    saw_flop: bool
    street_reached: str
    all_in: bool
    bb: float


def section_between(src: str, start_mark: str, end_marks: list[str]) -> str:
    if start_mark not in src:
        return ""
    body = src.split(start_mark, 1)[1]
    for em in end_marks:
        if em in body:
            body = body.split(em, 1)[0]
    return body


def parse_street_contrib(street_text: str, starting_commit: float = 0.0) -> float:
    already = starting_commit
    added = 0.0
    for line in street_text.splitlines():
        line = line.strip()
        if not line.startswith("Hero:"):
            continue
        m = re.match(
            r"Hero: posts (?:small blind|big blind|missed blind|the ante) \$([\d.]+)",
            line,
        )
        if m:
            amt = parse_money(m.group(1))
            added += amt
            already += amt
            continue
        m = re.match(r"Hero: posts small & big blinds \$([\d.]+)", line)
        if m:
            amt = parse_money(m.group(1))
            added += amt
            already += amt
            continue
        m = re.match(r"Hero: calls \$([\d.]+)", line)
        if m:
            amt = parse_money(m.group(1))
            added += amt
            already += amt
            continue
        m = re.match(r"Hero: bets \$([\d.]+)", line)
        if m:
            amt = parse_money(m.group(1))
            added += amt
            already += amt
            continue
        m = re.match(r"Hero: raises \$([\d.]+) to \$([\d.]+)", line)
        if m:
            to_amt = parse_money(m.group(2))
            add = to_amt - already
            if add < 0:
                add = parse_money(m.group(1))
            added += add
            already = to_amt
            continue
    return added


def parse_hand(text: str, source_file: str) -> Optional[HandResult]:
    if "Dealt to Hero" not in text:
        return None
    lines = [ln.rstrip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return None

    m = re.match(
        r"Poker Hand #(?P<id>\S+): Hold'em No Limit \(\$(?P<sb>[\d.]+)/\$(?P<bb>[\d.]+)\) - (?P<dt>.+)",
        lines[0],
    )
    if not m:
        # looser header
        m = re.match(
            r"Poker Hand #(?P<id>\S+):.*\(\$?(?P<sb>[\d.]+)/\$?(?P<bb>[\d.]+)\).*?- (?P<dt>.+)",
            lines[0],
        )
    if not m:
        return None

    hand_id = m.group("id")
    dt = m.group("dt").strip()
    bb = parse_money(m.group("bb"))

    table_m = re.search(r"Table '([^']+)'.*?Seat #(\d+) is the button", text)
    table = table_m.group(1) if table_m else ""
    button = int(table_m.group(2)) if table_m else 0

    seat_lines = re.findall(
        r"Seat (\d+): ([^\s(]+) \(\$([\d.]+) in chips\)", text
    )
    seats = [int(s[0]) for s in seat_lines]
    hero_seat = None
    for sid, name, _stack in seat_lines:
        if name == "Hero":
            hero_seat = int(sid)
            break
    if hero_seat is None:
        return None

    position = seat_positions(seats, button).get(hero_seat, "?")
    cards_m = re.search(r"Dealt to Hero \[([^\]]+)\]", text)
    cards = cards_m.group(1).strip() if cards_m else ""
    category = hand_category(cards) if cards else ""

    preflop = section_between(
        text,
        "*** HOLE CARDS ***",
        ["*** FLOP ***", "*** SHOWDOWN ***", "*** SUMMARY ***"],
    )
    flop_s = section_between(
        text, "*** FLOP ***", ["*** TURN ***", "*** SHOWDOWN ***", "*** SUMMARY ***"]
    )
    turn_s = section_between(
        text, "*** TURN ***", ["*** RIVER ***", "*** SHOWDOWN ***", "*** SUMMARY ***"]
    )
    river_s = section_between(
        text, "*** RIVER ***", ["*** SHOWDOWN ***", "*** SUMMARY ***"]
    )

    header_part = text.split("*** HOLE CARDS ***", 1)[0]
    put_in = parse_street_contrib(header_part, 0.0)
    blind_commit = 0.0
    for bm in re.finditer(
        r"Hero: posts (?:small blind|big blind|missed blind|the ante) \$([\d.]+)",
        header_part,
    ):
        blind_commit += parse_money(bm.group(1))
    m_both = re.search(r"Hero: posts small & big blinds \$([\d.]+)", header_part)
    if m_both:
        blind_commit = parse_money(m_both.group(1))

    put_in += parse_street_contrib(preflop, blind_commit)
    put_in += parse_street_contrib(flop_s, 0.0)
    put_in += parse_street_contrib(turn_s, 0.0)
    put_in += parse_street_contrib(river_s, 0.0)

    insurance = sum(
        parse_money(x)
        for x in re.findall(
            r"Hero: Pays All-in Insurance premium \(\$([\d.]+)\)", text
        )
    )
    insurance_payout = sum(
        parse_money(x)
        for x in re.findall(
            r"Hero: (?:Receives|Received|gets) All-in Insurance(?: payout)? \(\$([\d.]+)\)",
            text,
            re.I,
        )
    )
    returned = sum(
        parse_money(x)
        for x in re.findall(r"Uncalled bet \(\$([\d.]+)\) returned to Hero", text)
    )
    collected = sum(
        parse_money(x)
        for x in re.findall(r"Hero collected \$([\d.]+) from pot", text)
    )

    net_chip = round(
        collected + returned + insurance_payout - put_in - insurance, 2
    )

    pot_m = re.search(r"Total pot \$([\d.]+)", text)
    rake_m = re.search(r"Rake \$([\d.]+)", text)
    jp_m = re.search(r"Jackpot \$([\d.]+)", text)
    pot = parse_money(pot_m.group(1)) if pot_m else 0.0
    rake = parse_money(rake_m.group(1)) if rake_m else 0.0
    jackpot = parse_money(jp_m.group(1)) if jp_m else 0.0

    all_collected = sum(
        parse_money(x) for x in re.findall(r"collected \$([\d.]+) from pot", text)
    )
    if collected > 0 and all_collected > 0 and rake > 0:
        rake_share = round(rake * (collected / all_collected), 2)
    else:
        rake_share = 0.0
    net_norake = round(net_chip + rake_share, 2)

    # Preflop actions — line by line
    pre_actions: list[tuple[str, str]] = []
    for line in preflop.splitlines():
        line = line.strip()
        am = re.match(r"^([^:]+): (folds|checks|calls|bets|raises)(?:\s|$)", line)
        if not am:
            continue
        player = am.group(1).strip()
        if player.startswith("Dealt") or (" " in player and player != "Hero"):
            continue
        pre_actions.append((player, am.group(2)))

    hero_pre = [(p, a) for p, a in pre_actions if p == "Hero"]
    vpip = any(a in ("calls", "raises", "bets") for _, a in hero_pre)
    pfr = any(a == "raises" for _, a in hero_pre)

    three_bet = faced_raise = called_raise = fold_to_raise = False
    raise_seen = 0
    for player, act in pre_actions:
        if player == "Hero":
            if raise_seen >= 1:
                faced_raise = True
                if act == "folds":
                    fold_to_raise = True
                elif act == "calls":
                    called_raise = True
                elif act == "raises":
                    three_bet = True
            if act == "raises":
                raise_seen += 1
        elif act == "raises":
            raise_seen += 1

    summary = text.split("*** SUMMARY ***")[-1] if "*** SUMMARY ***" in text else ""
    hero_sum = ""
    for line in summary.splitlines():
        if "Hero" in line and line.strip().startswith("Seat"):
            hero_sum = line
            break

    if "folded before Flop" in hero_sum or "folded before flop" in hero_sum.lower():
        street_reached = "preflop"
        saw_flop = False
    elif "folded on the Flop" in hero_sum:
        street_reached, saw_flop = "flop", True
    elif "folded on the Turn" in hero_sum:
        street_reached, saw_flop = "turn", True
    elif "folded on the River" in hero_sum:
        street_reached, saw_flop = "river", True
    elif "showed" in hero_sum or "mucked" in hero_sum:
        street_reached, saw_flop = "showdown", True
    elif "won" in hero_sum or "collected" in hero_sum:
        if "*** RIVER ***" in text:
            street_reached, saw_flop = "river", True
        elif "*** TURN ***" in text:
            street_reached, saw_flop = "turn", True
        elif "*** FLOP ***" in text:
            street_reached, saw_flop = "flop", True
        else:
            street_reached, saw_flop = "preflop", False
    else:
        street_reached, saw_flop = "preflop", False
        if "*** FLOP ***" in text and "folded before Flop" not in hero_sum:
            if not re.search(r"Hero: folds", preflop or ""):
                saw_flop = True
                street_reached = "flop"

    went_to_showdown = "showed" in hero_sum or "mucked" in hero_sum
    won_at_showdown = went_to_showdown and (
        "won" in hero_sum or "collected" in hero_sum
    )
    all_in = bool(re.search(r"Hero:.*all-in", text))

    return HandResult(
        hand_id=hand_id,
        datetime=dt,
        table=table,
        file=source_file,
        position=position,
        cards=cards,
        category=category,
        players=len(seats),
        net_chip=net_chip,
        net_norake=net_norake,
        rake=rake,
        rake_share=rake_share,
        insurance=round(insurance, 2),
        jackpot=jackpot,
        pot=pot,
        vpip=vpip,
        pfr=pfr,
        three_bet=three_bet,
        faced_raise=faced_raise,
        fold_to_raise=fold_to_raise,
        called_raise=called_raise,
        went_to_showdown=went_to_showdown,
        won_at_showdown=won_at_showdown,
        saw_flop=saw_flop,
        street_reached=street_reached,
        all_in=all_in,
        bb=bb,
    )


def iter_txt_files(root: Path) -> Iterator[Path]:
    if root.is_file() and root.suffix.lower() == ".txt":
        yield root
        return
    if root.is_file() and root.suffix.lower() == ".zip":
        extract = root.with_suffix("") 
        extract = Path(str(root) + "_extracted")
        extract.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(root, "r") as zf:
            zf.extractall(extract)
        root = extract
    for p in sorted(root.rglob("*.txt")):
        yield p


def load_all(path: Path) -> list[HandResult]:
    hands: list[HandResult] = []
    for fp in iter_txt_files(path):
        raw = fp.read_text(encoding="utf-8", errors="replace")
        for part in re.split(r"(?=Poker Hand #)", raw):
            if not part.strip().startswith("Poker Hand #"):
                continue
            h = parse_hand(part, fp.name)
            if h:
                hands.append(h)
    seen: set[str] = set()
    unique: list[HandResult] = []
    for h in hands:
        if h.hand_id in seen:
            continue
        seen.add(h.hand_id)
        unique.append(h)
    return unique


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100.0 * n / d:.1f}%"


def bb100(net: float, hands: int, bb: float) -> str:
    if hands == 0 or bb <= 0:
        return "n/a"
    return f"{(net / bb) / hands * 100:.1f}"


def print_report(hands: list[HandResult]) -> dict:
    n = len(hands)
    if n == 0:
        print("No hands parsed.")
        return {}
    bb = hands[0].bb or 0.5
    chip = sum(h.net_chip for h in hands)
    norake = sum(h.net_norake for h in hands)
    ins = sum(h.insurance for h in hands)
    rs = sum(h.rake_share for h in hands)
    vpip_n = sum(1 for h in hands if h.vpip)
    saw_n = sum(1 for h in hands if h.saw_flop)
    pfr_n = sum(1 for h in hands if h.pfr)
    wtsd = sum(1 for h in hands if h.went_to_showdown)

    print("=" * 64)
    print("Hand history summary (dual EV)")
    print("=" * 64)
    print(f"Hands:              {n}")
    print(f"net_chip (w/ rake): ${chip:+.2f}   BB/100={bb100(chip, n, bb)}")
    print(f"net_norake:         ${norake:+.2f}   BB/100={bb100(norake, n, bb)}")
    print(f"rake_share total:   ${rs:.2f}")
    print(f"insurance total:    ${ins:.2f}")
    print(f"VPIP:               {pct(vpip_n, n)}")
    print(f"Saw flop:           {pct(saw_n, n)}   (= platform 翻牌% if GG)")
    print(f"PFR:                {pct(pfr_n, n)}")
    print(f"WTSD:               {pct(wtsd, n)}")
    print()
    print(
        f"{'Pos':<5} {'H':>4} {'VPIP':>7} {'Saw':>7} {'PFR':>7} "
        f"{'chip$':>10} {'norake$':>10}"
    )
    for pos in POSITION_ORDER:
        sub = [h for h in hands if h.position == pos]
        if not sub:
            continue
        sn = len(sub)
        print(
            f"{pos:<5} {sn:>4} {pct(sum(h.vpip for h in sub), sn):>7} "
            f"{pct(sum(h.saw_flop for h in sub), sn):>7} "
            f"{pct(sum(h.pfr for h in sub), sn):>7} "
            f"{sum(h.net_chip for h in sub):>+10.2f} "
            f"{sum(h.net_norake for h in sub):>+10.2f}"
        )

    return {
        "hands": n,
        "net_chip": round(chip, 2),
        "net_norake": round(norake, 2),
        "rake_share": round(rs, 2),
        "insurance": round(ins, 2),
        "vpip": round(100 * vpip_n / n, 2),
        "saw_flop": round(100 * saw_n / n, 2),
        "pfr": round(100 * pfr_n / n, 2),
        "wtsd": round(100 * wtsd / n, 2),
        "bb100_chip": bb100(chip, n, bb),
        "bb100_norake": bb100(norake, n, bb),
    }


def write_csv(hands: list[HandResult], path: Path) -> None:
    fields = list(asdict(hands[0]).keys()) if hands else []
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for h in sorted(hands, key=lambda x: x.datetime):
            w.writerow(asdict(h))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Parse poker hand histories (dual EV)")
    ap.add_argument("path", type=Path, help="Directory, .txt, or .zip of hand histories")
    ap.add_argument("--csv", type=Path, default=None, help="Write per-hand CSV")
    ap.add_argument(
        "--json-summary", action="store_true", help="Also print JSON summary line"
    )
    args = ap.parse_args(argv)

    if not args.path.exists():
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 1

    hands = load_all(args.path)
    summary = print_report(hands)
    if args.csv and hands:
        write_csv(hands, args.csv)
        print(f"\nCSV written: {args.csv}")
    if args.json_summary:
        print(json.dumps(summary, ensure_ascii=False))
    return 0 if hands else 2


if __name__ == "__main__":
    raise SystemExit(main())
