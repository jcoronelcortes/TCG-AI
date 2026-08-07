"""Census of the opposing ABILITIES that add flat damage to their attacks.

Sibling of `utils/op_scaling_census.py` and it exists for the same reason: a
table of ids rots silently. That one audits the attacks whose printed number is a
placeholder; this one audits the bonus that is not on the attacker at all -- a
body sitting on THEIR BENCH whose ability boosts the whole team.

The failure it guards against is `records/registro_004` step 30 (episode
90593852, vs Cynthia's Garchomp): their Gabite used Dragonslice, which PRINTS 40,
and the engine took 70 off our Tapu Bulu, which had 70 left. The extra 30 was
Cynthia's Roserade on their bench. Nothing in the agent read it, so every
defensive rule answered "it survives" and the turn's energy went onto a body that
was knocked out with the Grass still on it.

It scans every opposing deck in the repo, keeps the cards whose ABILITY text adds
flat damage, and splits them into four buckets:

    EQUIPO       already in OP_TEAM_DAMAGE_BUFF (a body in play buffs its team)
    PROPIO       already in OP_ACTIVE_ABILITY_DAMAGE (the attacker buffs itself)
    HERRAMIENTA  a tool, read where the attacker is read (ptcg/calc/damage.py)
    SIN MODELAR  nobody reads it -> decide what to do

A new entry in SIN MODELAR is not automatically a bug to fix; it is the same
question the sibling census asks. Can the agent READ the number off the board?
A body in play with an unconditional bonus, yes. A Supporter that lasts "during
this turn" and lives in their hand until it is played, no -- projecting it means
assuming a card we cannot see.

Usage:
    python utils/op_buff_census.py             # the four buckets
    python utils/op_buff_census.py --unmodelled    # only what is missing (exit 1 if any)
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

from cg.api import all_card_data  # noqa: E402
from ptcg.cards.ids import (OP_ACTIVE_ABILITY_DAMAGE,  # noqa: E402
                            OP_TEAM_DAMAGE_BUFF)

# "do 30 more damage", "does 100 more damage". Deliberately broad: a false
# positive costs one reading, a false negative costs a game.
_BUFF = re.compile(r"\bdo(?:es)?\s+\d+\s+more damage", re.IGNORECASE)

# Buffs that are NOT modelled ON PURPOSE, with the reason.
_EXCLUDED = {
    1141: "it lasts 'during this turn' and lives in their HAND until played "
          "(Premium Power Pro)",
    1211: "it lasts 'during this turn' and lives in their HAND until played "
          "(Black Belt's Training)",
    1191: "it lasts 'during this turn', lives in their HAND, and the opponent "
          "chooses which of the two halves to use (Kieran)",
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
    counts, n_decks = opposing_card_ids()

    rows = []
    for card_id, n in counts.items():
        card = cards.get(card_id)
        if card is None:
            continue
        for skill in (getattr(card, "skills", None) or []):
            text = getattr(skill, "text", None)
            if not text or not _BUFF.search(text):
                continue
            if card_id in OP_TEAM_DAMAGE_BUFF:
                bucket = "EQUIPO"
            elif card_id in OP_ACTIVE_ABILITY_DAMAGE:
                bucket = "PROPIO"
            elif card_id in _EXCLUDED:
                bucket = "EXCLUIDO"
            elif getattr(card, "cardType", None) != 0:
                # Not a Pokemon: a tool or a trainer. The tools ride on the
                # attacker and are read where the attacker is read.
                bucket = "HERRAMIENTA"
            else:
                bucket = "SIN MODELAR"
            rows.append((bucket, n, card.name, card_id,
                         getattr(skill, "name", "?"), text.replace("\n", " ")))
    rows.sort(key=lambda r: (r[0], -r[1]))
    return rows, n_decks


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--unmodelled", action="store_true",
                        help="solo lo que falta; sale con 1 si hay algo")
    args = parser.parse_args(argv)

    rows, n_decks = census()
    missing = [r for r in rows if r[0] == "SIN MODELAR"]

    if not args.unmodelled:
        print(f"{n_decks} mazos rivales, {len(rows)} buffs de daño\n")
        for bucket, n, name, cid, skill, text in rows:
            print(f"[{bucket:11s}] {n:3d} mazos  {name[:26]:28s} "
                  f"id={cid:<6d} {skill[:24]}")
            if bucket != "EQUIPO":
                print(f"                 {text[:130]}")
                if bucket == "EXCLUIDO":
                    print(f"                 motivo: {_EXCLUDED[cid]}")
        print("\nresumen: " + ", ".join(
            f"{b}={sum(1 for r in rows if r[0] == b)}"
            for b in ("EQUIPO", "PROPIO", "HERRAMIENTA", "EXCLUIDO",
                      "SIN MODELAR")))
        return 0

    for _, n, name, cid, skill, text in missing:
        print(f"{n:3d} mazos  {name} / {skill} (id {cid})")
        print(f"          {text}")
    if missing:
        print(f"\n{len(missing)} buffs de daño y nadie los lee")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
