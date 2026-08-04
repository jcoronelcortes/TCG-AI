"""Rebuilds a 60-card opposing deck from the local records.

It scans the opponent's VISIBLE zones in records/*.json (field, discard,
stadium; the copies are counted by serial, which is unique per card of the
game) and AMPLIFIES the partial list up to 60 cards by rule:

  - each Pokemon seen        -> 4 copies
  - each Trainer seen        -> 4 copies (Item/Tool/Supporter/Stadium)
  - each SPECIAL energy      -> 4 copies
  - ACE SPEC cards           -> 1 copy (a game rule, aceSpec in CardData)
  - filler up to 60          -> the most frequently seen BASIC energy

It does not claim to be the opponent's exact deck: it is a deterministic and legal
REFERENCE DECK for the --opponent mode of utils/selfplay.py (the differential
winrate of two versions of main.py against the same fixed opponent).

Usage:
    python utils/harvest_opponent_deck.py --output deck/opponents/crustle.csv
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_TESTS = _ROOT / "tests"
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from cg.api import CardType, all_card_data
from golden_corpus import our_index


def harvest_series(paths):
    """{serial: card_id} of every OPPOSING card seen.

    Our own seat is decided by a vote against deck.csv (`our_index`,
    mirroring the golden corpus): we are not always player 0. It used to read
    `step[0]` (the perspective of seat 0, which can be the OPPONENT) and
    filtered by `serial >= 60` (the serials are per player, so that
    also assumed ours were 0-59): in an episode played from
    seat 1 the result was a copy of OUR OWN deck. Each card
    carries a `playerIndex`, so ownership is read from there.
    """
    serials = {}

    def ver(c, opponent):
        if (c and c.get("serial") is not None
                and c.get("playerIndex") == opponent):
            serials[(opponent, c["serial"])] = c["id"]

    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        yo = our_index(data)
        opponent = 1 - yo
        for step in data.get("steps", []):
            obs = None
            for item in step:
                _o = item.get("observation") or {}
                if (_o.get("current") or {}).get("yourIndex") == yo:
                    obs = _o
                    break
            if obs is None:
                continue
            cur = obs.get("current")
            if not cur:
                continue
            op = cur["players"][opponent]
            for p in (op.get("active") or []) + (op.get("bench") or []):
                if not p:
                    continue
                ver(p, opponent)
                for c in (p.get("energyCards", []) + p.get("tools", [])
                          + p.get("preEvolution", [])):
                    ver(c, opponent)
            for c in op.get("discard", []):
                ver(c, opponent)
            for c in (cur.get("stadium") or []):
                ver(c, opponent)
    return serials


def amplificar(conteo_visto, tabla):
    """Amplifies the observed count up to 60 cards according to the documented rule."""
    deck = []
    basicas = {}
    for cid, visto in sorted(conteo_visto.items()):
        data = tabla.get(cid)
        if data is None:
            continue
        tipo = data.cardType
        if tipo == int(CardType.BASIC_ENERGY):
            basicas[cid] = visto
        else:
            copias = 1 if getattr(data, "aceSpec", False) else 4
            deck.extend([cid] * copias)
    if len(deck) > 60:
        raise SystemExit(
            f"la amplificacion x4 produce {len(deck)} cartas (>60): recorta "
            f"a mano la lista de vistos o ajusta la regla")
    relleno = 60 - len(deck)
    if not basicas:
        raise SystemExit("no se vio ninguna energia basica para el relleno")
    basica = max(basicas, key=basicas.get)
    deck.extend([basica] * relleno)
    return deck, basica, relleno


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True,
                    help="target csv (one card id per line, 60 lines)")
    ap.add_argument("--records", default="records",
                    help="folder holding the registro_*.json records")
    args = ap.parse_args(argv)

    paths = sorted((_ROOT / args.records).glob("registro_*.json"))
    if not paths:
        raise SystemExit(f"no hay registros en {args.records}/")
    serials = harvest_series(paths)
    conteo = defaultdict(int)
    for cid in serials.values():
        conteo[cid] += 1

    tabla = {c.cardId: c for c in all_card_data()}
    deck, basica, relleno = amplificar(conteo, tabla)

    print(f"Opponent cards seen ({sum(conteo.values())} en "
          f"{len(paths)} registros):")
    for cid, visto in sorted(conteo.items()):
        d = tabla.get(cid)
        in_deck = deck.count(cid)
        print(f"  {cid:>5} visto x{visto} -> in deck x{in_deck}  "
              f"{d.name if d else '?'}")
    print(f"Relleno: {relleno} x {tabla[basica].name}({basica})")

    output = _ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(str(c) for c in deck) + "\n")
    print(f"Written {output} ({len(deck)} cards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
