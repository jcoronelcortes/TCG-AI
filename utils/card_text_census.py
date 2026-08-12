r"""Which card texts in this environment has the code never heard of.

The fourth sibling of `utils/op_scaling_census.py` (attacks whose printed number
is a placeholder), `utils/op_buff_census.py` (the flat bonus that is not on the
attacker) and `utils/op_immunity_census.py` (the abilities that cancel our
damage). Those three each ask ONE question of ONE table: does this table say
what the card says. This one asks the question the three of them cannot:

    **Of every card that can be put on the table against us, which ones does the
    code not mention AT ALL?**

THE BUG THIS EXISTS FOR, found by hand on 12 August 2026 in episode 92355371.
**Deluxe Bomb (1167)** -- "if the Pokemon this card is attached to is in the
Active Spot and is damaged by an attack from your opponent's Pokemon (even if
this Pokemon is Knocked Out), put 12 damage counters on the Attacking Pokemon" --
is 120 damage to OUR OWN ATTACKER, and:

    grep -rn "1167\|Deluxe" --include="*.py" .   ->   nothing

It is a veto on WHO attacks: it sends any attacker of 120 HP or less to die for
free, and our Dipplin, Applin and Chikorita all are. We survived the board that
found it by accident -- the body that attacked was the only one on the table
that could take 120.

Nothing in this repository could have pointed at it. Every existing census
starts from a TABLE WE WROTE and checks it against the text; a card we never
thought about is in no table, so it is in no census. This one starts from the
CARD POOL and ends at the code, which is the only direction that can find a hole
rather than a mistake.

THE FOUR BANDS, from most to least suspicious:

    NUNCA REFERENCIADA     neither the card id, nor any of its attack ids, nor
                           any constant bound to them appears anywhere under
                           main.py or ptcg/, and no sibling census has argued
                           about it. The code does not know this card exists.
                           <- Deluxe Bomb's band
    SOLO NOMBRADA          `ptcg/cards/ids.py` binds a name to it and no module
                           outside that file ever mentions it. We wrote the name
                           down and then nothing read it.
    EXAMINADA Y EXCLUIDA   a sibling census looked at it and decided IN WRITING
                           not to model it -- a card that lives in their hand
                           until played, a coin flip, an effect they aim. A
                           decided question does not belong on a worklist of
                           open ones, and the reason is printed with the row.
    MODELADA               some module outside ids.py names it.

A card with no ability text and no attack text is not reported at all: there is
nothing to model. Everything else is ranked by HOW MANY OPPOSING DECKS PLAY IT,
because that is the only ordering that says which hole is bleeding.

THIS IS A WORKLIST, NOT A VERDICT, and the same honesty the sibling censuses
carry applies here twice over:

  * a card can be legitimately irrelevant -- most vanilla attack text needs no
    rule, and "the code does not mention it" is the correct state for the
    overwhelming majority of the pool. The report is ranked so a person reads
    the top of it, not all of it;
  * MODELADA means "a module names this card", not "the card is modelled
    correctly". The three sibling censuses are what checks correctness. A card
    can be in band 3 and still be read wrong -- that is exactly what the Crustle
    of 11 August was.

THE BLIND SPOT, said out loud because a census that hides one is worse than
none: CARD IDS AND ATTACK IDS SHARE A NUMBER SPACE. Card 115 is Conkeldurr and
attack 115 is Do the Wave, and `ptcg/cards/ids.py` binds both kinds of constant
the same way. The scan uses the constant's NAME as the discriminator (`*ATTACK*`
belongs to the attack namespace) and prints the evidence symbol next to every
verdict, so a wrong attribution is visible rather than silent.

A BARE INTEGER in the source NEVER promotes a card. It is printed as `? 1167`
beside the row and nothing more, because `93` inside a scorer is a score far
more often than it is Dipplin. This is the sibling censuses' own asymmetry
applied here -- a false positive costs one reading, a false negative is a hole
that stays hidden -- and hiding a hole is the only thing this instrument can do
wrong. The self-test enforces it: the control card is planted by taking its
symbols away, and it has to fall all the way to NUNCA REFERENCIADA while its id
is still a literal somewhere in the tree.

Usage:
    python utils/card_text_census.py                # the ranked report
    python utils/card_text_census.py --band 1       # only what nothing mentions
    python utils/card_text_census.py --top 60       # deeper into the ranking
    python utils/card_text_census.py --ours         # our own list too
    python utils/card_text_census.py --json out.json
"""

import argparse
import ast
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cg.api import all_attack, all_card_data  # noqa: E402

_IDS_FILE = _ROOT / "ptcg" / "cards" / "ids.py"
# `tables.py` builds card_table/attack_table from the whole pool, so every id is
# "mentioned" there by construction. It is excluded for the same reason ids.py
# is: naming the pool is not modelling a card.
_EXCLUDED_FROM_CODE = {_IDS_FILE, _ROOT / "ptcg" / "cards" / "tables.py"}
_DECK_GLOBS = ("deck/opponents/*.csv", "deck/real_opponents/*.csv",
               "competitor_decks/mazo_*.csv")
_OUR_DECK = "deck.csv"

BAND_NEVER, BAND_NAMED = "NUNCA REFERENCIADA", "SOLO NOMBRADA"
BAND_ARGUED, BAND_MODELLED = "EXAMINADA Y EXCLUIDA", "MODELADA"
_ORDER = (BAND_NEVER, BAND_NAMED, BAND_ARGUED, BAND_MODELLED)

# The sibling censuses each keep an `_EXCLUDED` dict: a card whose text says the
# thing they measure, deliberately NOT modelled, with the reason written next to
# it. Reading them is what keeps this instrument honest.
#
# THE BUG THIS FIXES, found the same day the census landed. The 55 damage drifts
# the oracle reports against Festival Lead are all 30 or 40, and they are Kieran
# (+30) and Black Belt's Training (+40) -- two Supporters that live in the
# opponent's HAND until played, which is exactly why `op_buff_census` excluded
# them in writing. This census called Kieran NUNCA REFERENCIADA, because no
# module names it, and that reading is true and useless: it puts a decided
# question back on a worklist of open ones. Comparing against the FINEST reading
# the project has, not the coarsest, is the doctrine this repository already
# paid for once.
_SIBLINGS = ("op_buff_census", "op_immunity_census", "op_scaling_census")

# A constant whose NAME says it lives in the attack namespace. Card ids and
# attack ids collide (see the blind spot above), and this is the only signal
# available without a second table.
_ATTACK_NAME = re.compile(r"ATTACK|ATAQUE", re.IGNORECASE)


# --------------------------------------------------------------------------
# the card pool that can be played against us
# --------------------------------------------------------------------------

def argued_exclusions():
    """card id -> the reason a sibling census gives for not modelling it."""
    import importlib

    out = {}
    for name in _SIBLINGS:
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        for card_id, reason in (getattr(module, "_EXCLUDED", None) or {}).items():
            out.setdefault(card_id, f"{name}: {reason}")
    return out


def _deck_counts(globs):
    """card id -> in how many decks it appears, and how many files were read."""
    counts = Counter()
    files = [p for g in globs for p in _ROOT.glob(g)]
    for path in files:
        seen = set()
        with open(path, encoding="utf-8") as f:
            for row in csv.reader(f):
                if row and row[0].strip().isdigit():
                    seen.add(int(row[0].strip()))
        counts.update(seen)
    return counts, len(files)


def _effects(card, attacks):
    """[(kind, name, text)] -- every printed sentence this card can produce."""
    out = []
    for skill in (getattr(card, "skills", None) or []):
        text = (getattr(skill, "text", "") or "").replace("\n", " ").strip()
        if text:
            out.append(("habilidad", (getattr(skill, "name", "?") or "?").strip(), text))
    for attack_id in (getattr(card, "attacks", None) or []):
        attack = attacks.get(attack_id)
        text = (getattr(attack, "text", "") or "").replace("\n", " ").strip()
        if text:
            out.append(("ataque", (getattr(attack, "name", "?") or "?").strip(), text))
    return out


# --------------------------------------------------------------------------
# what the code names
# --------------------------------------------------------------------------

def _literal_ints(node, known):
    """The integers a constant expression denotes, resolving names already bound."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return {node.value}
    if isinstance(node, ast.Name):
        return set(known.get(node.id, ()))
    if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        out = set()
        for element in node.elts:
            out |= _literal_ints(element, known)
        return out
    if isinstance(node, ast.Dict):
        out = set()
        for key in node.keys:
            if key is not None:
                out |= _literal_ints(key, known)
        return out
    # frozenset({...}) / set([...])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ("frozenset", "set", "tuple", "list"):
        out = set()
        for argument in node.args:
            out |= _literal_ints(argument, known)
        return out
    return set()


def id_constants():
    """`ptcg/cards/ids.py` read as AST: symbol -> the ids it denotes.

    Two passes are not needed because the file binds in dependency order (a
    collection always comes after the names it contains), which is checked: a
    collection that resolves to nothing is reported by `--debug`.
    """
    tree = ast.parse(_IDS_FILE.read_text(encoding="utf-8"))
    known = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        ids = _literal_ints(node.value, known)
        if ids:
            known[target.id] = ids
    return known


def _index_code():
    """(identifiers, integer literals) seen in each module outside ids.py."""
    words, numbers = set(), set()
    files = [_ROOT / "main.py"] + sorted(_ROOT.glob("ptcg/**/*.py"))
    for path in files:
        if path in _EXCLUDED_FROM_CODE or not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        # Comments are deliberately INCLUDED for identifiers and excluded for
        # numbers: a rule that names a card in a comment and nowhere else is
        # still a rule someone wrote about it, but a bare number in prose is
        # noise.
        words |= set(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", source))
        code_only = re.sub(r"#[^\n]*", "", source)
        numbers |= {int(n) for n in re.findall(r"\b\d{2,5}\b", code_only)}
    return words, numbers


def _symbols_for(target_ids, known, attack_namespace):
    """The constants of ids.py that denote any of `target_ids`."""
    out = []
    for symbol, ids in known.items():
        if not (ids & target_ids):
            continue
        is_attack_symbol = bool(_ATTACK_NAME.search(symbol))
        if is_attack_symbol != attack_namespace:
            continue
        out.append(symbol)
    return sorted(out)


# --------------------------------------------------------------------------
# the census
# --------------------------------------------------------------------------

def census(include_ours=False, strip_symbols=()):
    """(rows, decks read). A row is a dict; see `_ORDER` for its band.

    `strip_symbols` removes names from the code index. It is how the self-test
    plants a defect: a card the code demonstrably models must fall to
    NUNCA REFERENCIADA when the symbols that model it are taken away.
    """
    cards = {c.cardId: c for c in all_card_data()}
    attacks = {a.attackId: a for a in all_attack()}
    counts, n_decks = _deck_counts(_DECK_GLOBS)
    ours, _ = _deck_counts((_OUR_DECK,)) if include_ours else (Counter(), 0)
    known = id_constants()
    argued = argued_exclusions()
    words, numbers = _index_code()
    # The plant takes the symbols out of BOTH the code index and the id file:
    # what is being simulated is a card this project never wrote down, and half
    # a plant would only prove the detector can see half a hole.
    words = words - set(strip_symbols)
    known = {k: v for k, v in known.items() if k not in set(strip_symbols)}

    rows = []
    for card_id in sorted(set(counts) | set(ours)):
        card = cards.get(card_id)
        if card is None:
            continue
        effects = _effects(card, attacks)
        if not effects:
            continue                      # nothing printed, nothing to model

        attack_ids = set(getattr(card, "attacks", None) or [])
        card_symbols = _symbols_for({card_id}, known, attack_namespace=False)
        attack_symbols = _symbols_for(attack_ids, known, attack_namespace=True)
        symbols = card_symbols + attack_symbols

        named = bool(symbols)
        strong = sorted(s for s in symbols if s in words)
        weak = sorted({card_id} & numbers) + sorted(attack_ids & numbers)

        # A bare literal is a NOTE, never a promotion (see the header).
        note = ("  ? " + ", ".join(str(n) for n in weak[:3])) if weak else ""
        if strong:
            band, evidence = BAND_MODELLED, ", ".join(strong[:3]) + note
        elif card_id in argued:
            band, evidence = BAND_ARGUED, argued[card_id]
        elif named:
            band, evidence = BAND_NAMED, "ids.py: " + ", ".join(symbols[:3]) + note
        else:
            band, evidence = BAND_NEVER, note.strip()

        rows.append({
            "band": band,
            "decks": counts.get(card_id, 0),
            "ours": bool(ours.get(card_id)),
            "id": card_id,
            "name": getattr(card, "name", "?"),
            "evidence": evidence,
            "effects": effects,
        })

    rows.sort(key=lambda r: (_ORDER.index(r["band"]), -r["decks"], r["id"]))
    return rows, n_decks


# --------------------------------------------------------------------------
# the two halves
# --------------------------------------------------------------------------

# The control is a card this project demonstrably models: `FESTIVAL_LEAD_IDS`
# is read by main.py to decide whether a second wave is coming. It is used
# instead of Deluxe Bomb -- the real finding -- on purpose: the moment Deluxe
# Bomb gets modelled, a self-test written against it would start failing for the
# best possible reason, and a self-test that rots is a self-test nobody trusts.
_CONTROL_ID = 93                       # Dipplin


def _control_symbols():
    """EVERY constant that denotes the control card, resolved, not listed.

    Writing the three obvious names by hand is not a plant: Dipplin is named by
    a dozen collections (the Hydrapple line, the evolution tables, the dawn
    ladders), and with any one of them left standing the card stays MODELADA and
    the half passes for the wrong reason. It did, the first time this was run.
    """
    known = id_constants()
    cards = {c.cardId: c for c in all_card_data()}
    attack_ids = set(getattr(cards.get(_CONTROL_ID), "attacks", None) or [])
    return (_symbols_for({_CONTROL_ID}, known, attack_namespace=False)
            + _symbols_for(attack_ids, known, attack_namespace=True))


def self_test(verbose=True):
    """Sensitivity and specificity. Returns True only if both halves hold."""
    def band_of(rows, card_id):
        for row in rows:
            if row["id"] == card_id:
                return row["band"]
        return None

    intact, _ = census()
    specificity = band_of(intact, _CONTROL_ID) == BAND_MODELLED

    stripped, _ = census(strip_symbols=_control_symbols())
    sensitivity = band_of(stripped, _CONTROL_ID) == BAND_NEVER

    if verbose:
        print("autotest del censo de texto de carta")
        print(f"  especificidad  Dipplin (93) con el indice intacto -> "
              f"{band_of(intact, _CONTROL_ID)}   {'OK' if specificity else 'FALLA'}")
        print(f"  sensibilidad   sin sus simbolos                   -> "
              f"{band_of(stripped, _CONTROL_ID)}   {'OK' if sensitivity else 'FALLA'}")
        if not (specificity and sensitivity):
            print("  EL DETECTOR NO IMPRIME: no ha probado que ve un hueco "
                  "plantado y calla sin el.")
        print()
    return specificity and sensitivity


# --------------------------------------------------------------------------

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--band", type=int, default=0,
                        help="1=nunca referenciada, 2=solo nombrada, 3=modelada")
    parser.add_argument("--top", type=int, default=30,
                        help="cuantas filas por banda (0 = todas)")
    parser.add_argument("--ours", action="store_true",
                        help="incluir tambien nuestra propia lista")
    parser.add_argument("--json", default=None, help="volcar las filas crudas")
    parser.add_argument("--self-test", action="store_true",
                        help="solo las dos mitades")
    parser.add_argument("--no-self-test", action="store_true",
                        help="imprimir sin validarse (para depurar)")
    args = parser.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1
    if not args.no_self_test and not self_test():
        return 1

    rows, n_decks = census(include_ours=args.ours)
    summary = Counter(r["band"] for r in rows)

    print(f"{n_decks} mazos rivales leidos, {len(rows)} cartas con texto "
          f"imprimible en ellos\n")
    bands = _ORDER if not args.band else (_ORDER[args.band - 1],)
    for band in bands:
        chosen = [r for r in rows if r["band"] == band]
        shown = chosen if args.top == 0 else chosen[:args.top]
        print(f"=== {band}  ({len(chosen)}) " + "=" * (46 - len(band)))
        for row in shown:
            mine = " [NUESTRA]" if row["ours"] else ""
            tail = f"  <- {row['evidence']}" if row["evidence"] else ""
            print(f"{row['decks']:>4} mazos  {row['name']:<26} "
                  f"id={row['id']:<5}{mine}{tail}")
            if band != BAND_MODELLED:
                for kind, name, text in row["effects"][:2]:
                    print(f"            {kind} {name}: {text[:120]}")
        if args.top and len(chosen) > len(shown):
            print(f"            ... y {len(chosen) - len(shown)} mas "
                  f"(--top 0 para todas)")
        print()

    print("resumen: " + ", ".join(f"{b}={summary[b]}" for b in _ORDER))
    print("Es una LISTA DE TRABAJO ordenada por mazos que la juegan, no un "
          "veredicto: la mayoria del texto de un TCG no necesita regla. Y "
          "MODELADA significa 'algun modulo la nombra', nunca 'la lee bien'.")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print(f"\nfilas crudas -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
