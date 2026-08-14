"""The delta between two saved matchup-matrix runs, matchup by matchup.

Two arms measured with the same `--seeds` over the same corpus played the same
games, so the honest comparison is PAIRED: the per-matchup difference and its
weighted mean, not the overlap of the two headline intervals. Two marginal
intervals can touch while every single matchup moved the same way, and they can
sit apart while the movement is three decks out of a hundred and thirty.

WHAT IT PRINTS, in the order the reading wants:

    the weighted delta in PRIZES        the axis with resolution: 18 of 22
                                        archetypes are above 92 % winrate and
                                        the winrate cannot rank them
    the weighted delta in WINRATE       for continuity with what is on record
    how many matchups moved at all      a delta carried by three decks is a
                                        different object from one carried by all
    the ten that moved most, each way

THE CAVEAT THIS TOOL CANNOT REMOVE, and the report has to carry it: common
random numbers collapse to exactly zero only where the change cannot act. An arm
that DECIDES differently desynchronises the engine's stream from that point on,
and two different LISTS desynchronise it from the first shuffle -- so a list
comparison keeps real variance and does not enjoy the seeded floor of a code
comparison. Pairing still removes the corpus and the allocation from the
difference, which is most of it.

Usage:
    python utils/compare_runs.py BASE.txt CANDIDATO.txt [--weights pesos.csv]
"""

import argparse
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from reweight_matrix import load_weights, parse_run  # noqa: E402


def paired(base, cand):
    """[{deck, d_wr, d_prem, n}] over the matchups both runs measured."""
    by_deck = {r["deck"]: r for r in base}
    out = []
    for r in cand:
        b = by_deck.get(r["deck"])
        if b is None:
            continue
        out.append({
            "deck": r["deck"],
            "d_wr": r["wr"] - b["wr"],
            "d_prem": (None if r["prem"] is None or b["prem"] is None
                       else r["prem"] - b["prem"]),
            "n": min(r["n"], b["n"]),
            "base_wr": b["wr"], "cand_wr": r["wr"],
            "base_prem": b["prem"], "cand_prem": r["prem"],
            "d_ff": r["ff"] - b["ff"],
        })
    return out


def weighted_delta(rows, weights, key):
    """(mean, se) of a per-matchup delta, weighted by meta share.

    The SE treats each matchup's delta as independent and estimates its variance
    from the two binomial arms; with common random numbers that OVERSTATES the
    error (the arms are positively correlated), so an interval that already
    excludes zero here excludes it in reality too.
    """
    num = den = var = 0.0
    for r in rows:
        w = weights.get(r["deck"], 0.0) if weights else 1.0
        d = key(r)
        if w <= 0 or d is None:
            continue
        num += w * d
        den += w
        if key is _wr:
            p1, p2, n = r["base_wr"], r["cand_wr"], max(1, r["n"])
            var += (w ** 2) * (p1 * (1 - p1) + p2 * (1 - p2)) / n
    if den <= 0:
        return None, None
    return num / den, (math.sqrt(var) / den if var else None)


def _wr(r):
    return r["d_wr"]


def _prem(r):
    return r["d_prem"]


def _archetypes(weights_path):
    """{deck stem: archetype} from the corpus's own pesos.csv."""
    import csv

    with open(weights_path, encoding="utf-8-sig") as fh:
        return {r["archivo"].removesuffix(".csv"): r.get("arquetipo", "?")
                for r in csv.DictReader(fh)}


def _by_archetype(rows, weights_path, weights):
    """The delta AGGREGATED by archetype, which is the view that ranks.

    A per-list table fragments an archetype across twenty rows and then reports
    each of them as a rounding error; the corpus of 500 exists because the same
    number aggregated names Crustle Wall as the largest leak. The same applies to
    a delta: twenty Crustle lists moving +1 each is a finding, and twenty rows of
    +1 at 0.2 % weight is not visibly anything.
    """
    arche = _archetypes(weights_path)
    agg = {}
    for r in rows:
        name = arche.get(r["deck"], "?")
        w = weights.get(r["deck"], 0.0) if weights else 1.0
        if w <= 0:
            continue
        a = agg.setdefault(name, {"w": 0.0, "wr": 0.0, "prem": 0.0, "n": 0})
        a["w"] += w
        a["wr"] += w * r["d_wr"]
        a["prem"] += w * (r["d_prem"] or 0.0)
        a["n"] += 1
    # Ordered by CONTRIBUTION (weight x delta), printed as the delta INSIDE the
    # archetype: +1.7 pp against 0.2 % of the meta is a smaller thing than
    # +0.6 pp against 17.8 %, and the ranking has to say so while the number
    # stays readable as "what happens when I sit down against this deck".
    print("\n  Por ARQUETIPO (delta dentro del arquetipo, ordenado por CONTRIBUCION):")
    for name, a in sorted(agg.items(), key=lambda kv: -abs(kv[1]["wr"])):
        if a["w"] <= 0:
            continue
        print(f"    {name:<34} {100 * a['wr'] / a['w']:+5.2f} pp   "
              f"premios {a['prem'] / a['w']:+.3f}   "
              f"peso {100 * a['w']:4.1f}%  ({a['n']} listas)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base")
    ap.add_argument("candidate")
    ap.add_argument("--weights", default=None,
                    help="pesos.csv; without it every matchup weighs the same")
    ap.add_argument("--label", default="", help="a line printed above the report")
    args = ap.parse_args(argv)

    base, cand = parse_run(args.base), parse_run(args.candidate)
    rows = paired(base, cand)
    if not rows:
        print("ERROR: the two runs share no matchup", file=sys.stderr)
        return 1
    weights = load_weights(args.weights) if args.weights else None

    if args.label:
        print(args.label)
    print(f"{len(rows)} matchups in common  "
          f"({len(base)} in the base, {len(cand)} in the candidate)"
          f"{'' if weights else '   [SIN PESOS: media simple]'}\n")

    d_prem, _ = weighted_delta(rows, weights, _prem)
    d_wr, se_wr = weighted_delta(rows, weights, _wr)
    if d_prem is not None:
        print(f"  PREMIOS   {d_prem:+.3f} por partida")
    if d_wr is not None:
        interval = (f"  [{100 * (d_wr - 1.96 * se_wr):+.2f}, "
                    f"{100 * (d_wr + 1.96 * se_wr):+.2f}]" if se_wr else "")
        print(f"  WINRATE   {100 * d_wr:+.2f} pp{interval}")

    moved = [r for r in rows if abs(r["d_wr"]) > 1e-9]
    print(f"\n  {len(moved)} de {len(rows)} matchups se movieron; "
          f"{len(rows) - len(moved)} identicos (misma semilla, misma decision)")
    ff = sum(r["d_ff"] for r in rows)
    print(f"  forfeits: {ff:+d}")

    if args.weights:
        _by_archetype(rows, args.weights, weights)

    for title, sign in (("Lo que MAS sube", -1), ("Lo que MAS baja", 1)):
        orden = sorted(moved, key=lambda r: sign * r["d_wr"])[:10]
        if not orden:
            continue
        print(f"\n  {title}:")
        for r in orden:
            peso = f"  peso {100 * weights.get(r['deck'], 0.0):4.1f}%" if weights else ""
            prem = "" if r["d_prem"] is None else f"  premios {r['d_prem']:+.2f}"
            print(f"    {r['deck']:<34} {100 * r['base_wr']:5.1f}% -> "
                  f"{100 * r['cand_wr']:5.1f}%  ({100 * r['d_wr']:+5.1f} pp)"
                  f"{prem}{peso}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
