"""Census of opposing attacks whose damage is NOT the number printed on the card.

`ptcg/cards/op_scaling.py` is a table of ids, and a table of ids rots silently:
the competition's card pool moves, a new opposing deck arrives in
`deck/real_opponents/` or `competitor_decks/`, and an attack that hits for 300
starts being projected as the "20x" placeholder it prints. That is the failure
that cost registro_013 (a Syrup Storm read as 30 while the engine dealt 270), and
nothing in the suite can catch it: the agent does not crash, it just walks into
the hit.

This is the audit. It scans every opposing deck in the repo, resolves each card's
attacks, keeps the ones whose text counts something ("... for each ..."), and
splits them into three buckets:

    MODELADO      already in OP_SCALING_DAMAGE
    SIN MODELAR   scales, and nobody is reading it -> decide what to do
    EXCLUIDO      knowingly left out (coin flips, the opponent's own discards)

A new entry in SIN MODELAR is not automatically a bug to fix: read the text and
ask the question the table's docstring asks -- can the agent READ the number off
the board, or would it be guessing? If it can, add it; if it cannot, add it to
_EXCLUDED here with the reason, so the next census does not re-raise it.

Usage:
    python utils/op_scaling_census.py            # the three buckets
    python utils/op_scaling_census.py --unmodelled   # only what is missing (exit 1 if any)
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cg.api import all_attack, all_card_data  # noqa: E402
from ptcg.cards.op_scaling import OP_SCALING_DAMAGE  # noqa: E402

# The text of an attack that counts something on the board. It is deliberately
# broad: a false positive costs one reading, a false negative costs a game.
_SCALES = re.compile(r"more damage for each|damage for each|times the number",
                     re.IGNORECASE)

# Attacks that scale but are NOT modelled ON PURPOSE, with the reason. See the
# docstring of ptcg/cards/op_scaling.py for the criterion.
_EXCLUDED = {
    1092: "coin flips (Rapid-Fire Combo); the +50 estimate was measured and reverted",
    717: "coin flips (Continuous Headbutt)",
    608: "the opponent chooses how much Energy to discard (Erasure Ball)",
    72: "the opponent chooses how much Energy to discard (Bellowing Thunder)",
}

_DECK_GLOBS = ("deck/opponents/*.csv", "deck/real_opponents/*.csv",
               "competitor_decks/mazo_*.csv")


def opposing_card_ids():
    """card id -> in how many opposing decks it appears."""
    counts = Counter()
    files = [p for g in _DECK_GLOBS for p in _ROOT.glob(g)]
    for path in files:
        seen = set()
        with open(path, encoding="utf-8") as f:
            for row in csv.reader(f):
                if row and row[0].strip().isdigit():
                    seen.add(int(row[0].strip()))
        counts.update(seen)
    return counts, len(files)


def census():
    cards = {c.cardId: c for c in all_card_data()}
    attacks = {a.attackId: a for a in all_attack()}
    counts, n_decks = opposing_card_ids()

    rows = []
    for card_id, n in counts.items():
        card = cards.get(card_id)
        if card is None:
            continue
        for attack_id in (getattr(card, "attacks", None) or []):
            atk = attacks.get(attack_id)
            if atk is None or not atk.text or not _SCALES.search(atk.text):
                continue
            if attack_id in OP_SCALING_DAMAGE:
                bucket = "MODELADO"
            elif attack_id in _EXCLUDED:
                bucket = "EXCLUIDO"
            else:
                bucket = "SIN MODELAR"
            rows.append((bucket, n, card.name, attack_id, atk.name,
                         atk.damage or 0, atk.text))
    rows.sort(key=lambda r: (r[0], -r[1]))
    return rows, n_decks


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--unmodelled", action="store_true",
                        help="only what is missing; exit 1 if there is any")
    args = parser.parse_args(argv)

    rows, n_decks = census()
    missing = [r for r in rows if r[0] == "SIN MODELAR"]

    if not args.unmodelled:
        print(f"{n_decks} mazos rivales, {len(rows)} ataques que escalan\n")
        for bucket, n, card, aid, aname, printed, text in rows:
            print(f"[{bucket:11s}] {n:3d} mazos  {card[:26]:28s} "
                  f"atk{aid:<5d} {aname[:22]:24s} impreso={printed}")
            if bucket != "MODELADO":
                print(f"                 {text[:130]}")
                if bucket == "EXCLUIDO":
                    print(f"                 motivo: {_EXCLUDED[aid]}")
        print(f"\nresumen: " + ", ".join(
            f"{b}={sum(1 for r in rows if r[0] == b)}"
            for b in ("MODELADO", "EXCLUIDO", "SIN MODELAR")))
        return 0

    for _, n, card, aid, aname, printed, text in missing:
        print(f"{n:3d} mazos  {card} / {aname} (atk {aid}, impreso {printed})")
        print(f"          {text}")
    if missing:
        print(f"\n{len(missing)} ataques escalan y nadie los lee")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
