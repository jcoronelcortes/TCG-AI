"""Census of the opposing abilities that CANCEL our damage, against the tables
that claim to model them.

The third sibling of `utils/op_scaling_census.py` (attacks whose printed number
is a placeholder) and `utils/op_buff_census.py` (the flat bonus that is not on
the attacker at all). All three exist for one reason: **a table of ids rots
silently.** The card text is the truth and the table is a copy of it, and nobody
was diffing the two here.

THE FAILURE IT GUARDS AGAINST, found by hand on 11 August 2026. `EX_IMMUNE_IDS`
carried `Crustle 533`, whose ability is **Sturdy** -- "if this Pokemon has full
HP and would be Knocked Out ... its remaining HP becomes 10" -- and not the
"Prevent all damage ... by attacks from your opponent's Pokemon {ex}" the table
is for. That is the OTHER Crustle: 345, the Fighting/Grass pair share a name and
nothing else. With 533 on the board we would have read every attack from our ex
as ZERO and walked around a 150 HP body that falls in one hit.

It cost nothing, because no deck in the corpus plays it -- which is the point of
running a census instead of arguing: the honest report was "0 of 87 lists", and
the fix is worth making because the meta rotates, not because it is bleeding.

THE FOUR TABLES, and what each one claims:

    EX_IMMUNE_IDS        prevents all damage from our {ex}
    ABILITY_IMMUNE_IDS   prevents all damage from Pokemon that HAVE an ability
    TERA_IMMUNE_IDS      prevents all damage from our TERA Pokemon
    FULL_HP_SURVIVE_IDS  at full HP, survives a lethal hit at 10 HP

A card in one of them whose text does not say that thing is a defect. A card
whose text DOES say it and is in no table is the other half, and the more
expensive one -- that is a wall we walk into.

THE SECOND FAILURE, 16 August 2026, and it was in this file's own reading.
Milotic ex's *Sparkling Scales* prevents all damage from the opponent's **Tera**
Pokemon -- our Teal Mask Ogerpon ex and no one else -- and it was a wall we
walked into for a whole game (episode 93490495). TWO things had to go wrong
together: there was no claim for that shape, so the text matched nothing; and
the search for unmodelled cards only ever read the cards the CORPUS DECKS play,
and Milotic ex is in 0 of the 408 lists. A card the meta plays and the corpus
does not was invisible twice over. `--all-cards` is the second half of the fix.

WHAT IT CANNOT DO, said out loud because a census that hides its blind spot is
worse than none: it matches ENGLISH TEXT with regular expressions. A card whose
wording is unusual reads as unmodelled and needs a human; that is why
`--unmodelled` prints the whole text rather than a verdict.

Usage:
    python utils/op_immunity_census.py                # the buckets, by exposure
    python utils/op_immunity_census.py --unmodelled   # only what is missing (exit 1 if any)
    python utils/op_immunity_census.py --all-cards --unmodelled   # ...in the WHOLE card table
    python utils/op_immunity_census.py --check        # exit 1 if a table is WRONG
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
from ptcg.cards.ids import (ABILITY_IMMUNE_IDS,  # noqa: E402
                            EX_IMMUNE_IDS, FULL_HP_SURVIVE_IDS,
                            TERA_IMMUNE_IDS)

# What each table claims, as the card would print it. Deliberately broad on the
# damage side and strict on the qualifier: a false positive costs one reading,
# a false negative costs a game.
_PREVENT = r"prevent all (?:of the )?damage"
_CLAIMS = {
    "EX_IMMUNE_IDS": (
        EX_IMMUNE_IDS,
        re.compile(_PREVENT + r".{0,80}?\{ex\}", re.IGNORECASE | re.DOTALL),
        "prevents all damage from our {ex}"),
    "ABILITY_IMMUNE_IDS": (
        ABILITY_IMMUNE_IDS,
        re.compile(_PREVENT + r".{0,80}?(?:have|has) (?:an )?(?:Abilit|abilit)",
                   re.IGNORECASE | re.DOTALL),
        "prevents all damage from Pokemon with an Ability"),
    "TERA_IMMUNE_IDS": (
        TERA_IMMUNE_IDS,
        re.compile(_PREVENT + r".{0,80}?\bTera\b", re.IGNORECASE | re.DOTALL),
        "prevents all damage from our TERA Pokemon"),
    "FULL_HP_SURVIVE_IDS": (
        FULL_HP_SURVIVE_IDS,
        re.compile(r"full HP and would be Knocked Out", re.IGNORECASE),
        "at full HP it survives at 10"),
}

# Immunities NOT modelled on purpose, with the reason. Same contract as the
# sibling censuses: an exclusion has to be argued in writing, here, or it is
# just a card nobody looked at.
_EXCLUDED = {
    # "You can use this card only if your opponent has 2 or fewer Prize cards
    # remaining. Choose 1 of your Pokemon in play. During your opponent's NEXT
    # TURN, prevent all damage from ... attacks done to that Pokemon by your
    # opponent's Pokemon {ex}."
    #
    # Same shape as Premium Power Pro and Black Belt's Training in the buff
    # census, and excluded for the same reason: it is a TRAINER that lives in
    # their hand until played, it lasts one turn, and THEY choose which of their
    # bodies it lands on. Modelling it means assuming a card we cannot see and a
    # target we cannot know. The board tells us nothing until it is on the
    # table, and by then the damage question is already answered.
    #
    # It is in 4 decks, which is why it gets a paragraph instead of silence.
    1228: "it lasts 'during your opponent's next turn', lives in their HAND "
          "until played, and THEY pick which body it protects "
          "(Acerola's Mischief)",
    # The two that `--all-cards` turns up and that ARE modelled -- just not by a
    # table of ids. Both are single cards with a qualifier no set can share, so
    # they are read by NAME in `_our_effective_damage` and `_ko_not_guaranteed`
    # respectively. They are listed here so that `--all-cards --unmodelled`
    # comes back empty and can be a gate: an exclusion that is not written down
    # is indistinguishable from a card nobody looked at.
    83: "Armor Tail is modelled by name (`Farigiraf_ex` + `OUR_BASIC_EX_IDS` in "
        "`_our_effective_damage`): it reads BASIC ex, which no existing table "
        "claims",
    1155: "Survival Brace is a TOOL and it is modelled by name "
          "(`Survival_Brace` in `_ko_not_guaranteed`): it does not prevent "
          "damage, it denies the knockout",
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


def _skills_text(card):
    """[(ability name, its text on one line)] for every ability the card prints."""
    return [((getattr(s, "name", "?") or "?").strip(),
             (getattr(s, "text", "") or "").replace("\n", " "))
            for s in (getattr(card, "skills", None) or [])]


def census(all_cards=False):
    """(rows, decks scanned). A row is (bucket, decks, name, id, table, skill, text).

    `all_cards` widens the SECOND half -- the search for immunities nobody
    models -- from "the cards the corpus decks play" to the whole card table.

    IT IS NOT A REFINEMENT, IT IS THE HOLE THIS CENSUS WAS FALLING THROUGH
    (user, episode 93490495, August 2026). Milotic ex prints an immunity against
    our Tera, the user met it on the ladder, and it appears in **0 of the 408**
    opposing lists in the corpus -- so the census, which only ever read cards
    seen in a deck file, reported "0 unmodelled" while the agent was swinging
    into it for zero. The corpus is a sample of the meta and the meta rotates
    faster than the sample; the card table does not.

    The narrow reading stays the default because it is the one that ranks by
    exposure ("in how many decks"), which is what decides whether a miss is
    urgent. This one answers the other question -- what is out there at all --
    and it is the one to run before a tournament, not before a commit.
    """
    cards = {c.cardId: c for c in all_card_data()}
    counts, n_decks = opposing_card_ids()
    if all_cards:
        for card_id in cards:
            counts.setdefault(card_id, 0)
    rows = []

    # Half one: every id the tables claim, checked against its own text.
    for tabla, (ids, patron, dice) in _CLAIMS.items():
        for card_id in sorted(ids):
            card = cards.get(card_id)
            if card is None:
                rows.append(("SIN CARTA", counts.get(card_id, 0), "?", card_id,
                             tabla, "-", f"la tabla dice '{dice}' y el id no existe"))
                continue
            textos = _skills_text(card)
            if any(patron.search(t) for _, t in textos):
                bucket = "OK"
            else:
                bucket = "TABLA EQUIVOCADA"
            skill, text = textos[0] if textos else ("(sin habilidad)", "")
            rows.append((bucket, counts.get(card_id, 0), card.name, card_id,
                         tabla, skill, text))

    # Half two, and the expensive one: text that claims an immunity nobody
    # models. A wall we do not know about is a wall we walk into.
    reclamados = {cid for ids, _, _ in _CLAIMS.values() for cid in ids}
    for card_id, n in counts.items():
        if card_id in reclamados or card_id in _EXCLUDED:
            continue
        card = cards.get(card_id)
        if card is None:
            continue
        for skill, text in _skills_text(card):
            for tabla, (_ids, patron, _dice) in _CLAIMS.items():
                if patron.search(text):
                    rows.append(("SIN MODELAR", n, card.name, card_id,
                                 tabla, skill, text))
                    break

    rows.sort(key=lambda r: (r[0], -r[1]))
    return rows, n_decks


ORDEN = ("TABLA EQUIVOCADA", "SIN MODELAR", "SIN CARTA", "OK")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--unmodelled", action="store_true",
                        help="solo lo que falta; sale con 1 si hay algo")
    parser.add_argument("--check", action="store_true",
                        help="sale con 1 si alguna tabla contradice el texto")
    parser.add_argument("--all-cards", action="store_true",
                        help="busca inmunidades sin modelar en TODA la tabla de "
                             "cartas, no solo en las que juegan los mazos del "
                             "corpus (Milotic ex sale en 0 de 408)")
    args = parser.parse_args(argv)

    rows, n_decks = census(all_cards=args.all_cards)
    interes = [r for r in rows if r[0] != "OK"]

    if args.unmodelled:
        faltan = [r for r in rows if r[0] == "SIN MODELAR"]
        for _b, n, name, cid, tabla, skill, text in faltan:
            print(f"{n:>4} mazos  {name} (id={cid})  parece de {tabla}")
            print(f"           {skill}: {text[:150]}")
        print(f"\n{len(faltan)} inmunidades sin modelar")
        return 1 if faltan else 0

    total = sum(len(ids) for ids, _, _ in _CLAIMS.values())
    print(f"{n_decks} mazos rivales, {total} ids en las {len(_CLAIMS)} tablas "
          f"de inmunidad\n")
    for bucket in ORDEN:
        for _b, n, name, cid, tabla, skill, text in [r for r in rows if r[0] == bucket]:
            print(f"[{bucket:<16}] {n:>3} mazos  {name:<28} id={cid:<6} {tabla}")
            if bucket != "OK":
                print(f"                     {skill}: {text[:110]}")
    resumen = Counter(r[0] for r in rows)
    print("\nresumen: " + ", ".join(f"{k}={resumen[k]}" for k in ORDEN if resumen[k]))
    if not interes:
        print(f"Las {len(_CLAIMS)} tablas dicen lo que dicen las cartas.")
    else:
        print("UNA TABLA QUE CONTRADICE EL TEXTO DE LA CARTA es un muro inventado "
              "o un muro invisible. Las dos se pagan en premios.")

    if args.check:
        malas = [r for r in rows if r[0] in ("TABLA EQUIVOCADA", "SIN CARTA")]
        return 1 if malas else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
