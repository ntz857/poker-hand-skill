# GGPoker hand history notes

## Header

```text
Poker Hand #HD…: Hold'em No Limit ($0.25/$0.5) - 2026/08/02 02:31:26
Table 'NLHPurple35' 6-max Seat #5 is the button
Seat 4: Hero ($89.75 in chips)
```

Hero is always labeled `Hero`. Other seats are anonymized hashes.

## Streets

Markers: `*** HOLE CARDS ***`, `*** FLOP ***`, `*** TURN ***`, `*** RIVER ***`, `*** SHOWDOWN ***`, `*** SUMMARY ***`.

Blinds are posted **before** `HOLE CARDS`.

## Raise format

```text
Hero: raises $0.75 to $1.25
```

Amount added this action = `to_amount − already_committed_on_street` (not the first dollar figure alone).

## Fees / extras (must handle)

| Line | Effect on net_chip |
|------|---------------------|
| `Rake $x` in Total pot line | Already reflected in `collected` (smaller pot) |
| `Jackpot $x` | Pot field only; usually not a separate Hero debit line |
| `Hero: posts missed blind $x` | **Debit** (real chips) |
| `Hero: Pays All-in Insurance premium ($x)` | **Debit** |
| `Uncalled bet ($x) returned to Hero` | Credit |
| `Hero collected $x from pot` | Credit |

## Platform UI vs parser

| UI label (CN) | Meaning |
|---------------|---------|
| 翻牌% | Saw flop % — **not** VPIP |
| 摊牌 / 摊牌% | Showdowns / WTSD |
| 输赢 | Often close to chip or pre-rake style; reconcile with stack walk |

## Position labels (this skill)

6-max full ring: SB, BB, UTG, HJ, CO, BTN (from seat after button).

Short-handed: drop middle seats (e.g. 5-handed: SB BB UTG CO BTN).
