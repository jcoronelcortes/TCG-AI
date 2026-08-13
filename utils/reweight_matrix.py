"""Re-reads a saved matchup matrix and re-weights it, without replaying a game.

The expensive part of `utils/matchup_matrix.py` is the per-matchup winrates; the
weighted summary on top of them is arithmetic. So a second meta model costs
nothing: this parses a saved run and reports it under as many weightings as there
are `pesos*.csv` files beside the corpus.

Two summaries this prints that the matrix cannot:

1. **The same run under two metas.** Field vs top-100 (see
   `utils/top100_weights.py` for why they differ). The rows where they disagree
   most are the first draft of what a playbook should prioritise, because they
   are the matchups whose importance depends on whether the goal is holding a
   ladder position or climbing it.

2. **The seat split, aggregated.** `matchup_matrix` prints it per matchup; the
   weighted aggregate is what says whether going first is worth anything across
   the meta rather than against one deck. This matters from 13 August 2026: until
   `8192c22` the agent vetoed going first, so every historical figure is the
   going-second half and the going-first half had never run at all.

A note on the interval. The weighted mean's SE is computed from the per-matchup
binomial variances, `sqrt(sum(w_i^2 p_i(1-p_i)/n_i)) / sum(w_i)`. It assumes the
matchups are independent, which they are (different opponents, separate games),
but it does NOT include the uncertainty of the WEIGHTS themselves -- the meta
shares are treated as known. With 99 decks in the top-100 band, that assumption
is the weaker half of the top-100 interval and the report should say so.

Usage:
    python utils/reweight_matrix.py log/noche-.../M1-baseline_campo.txt
    python utils/reweight_matrix.py <run.txt> --corpus deck/real_opponents_500
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# `  alakazam_1: 95.8% [95.2-96.2] premios +3.69 (n=5628, forfeits nuestros 0)
#     asiento: primero 96.0% (2702/2814) segundo 95.5% (2687/2814)`
_ROW = re.compile(
    r"^\s+(?P<deck>\S+): (?P<wr>[\d.]+)% \[[\d.]+-[\d.]+\]"
    r"(?: premios (?P<prem>[+-][\d.]+))?"
    r" \(n=(?P<n>\d+), forfeits nuestros (?P<ff>\d+)\)"
    r"(?:\s+asiento: primero (?:(?P<w1>\d+)/(?P<n1>\d+)|sin partidas)"
    r" segundo (?:(?P<w2>\d+)/(?P<n2>\d+)|sin partidas))?"
)
# The seat counts sit inside parentheses after the percentage; capture them by a
# second pass rather than complicating the row pattern.
_SEAT = re.compile(r"asiento: primero (?:[\d.]+% \((\d+)/(\d+)\)|sin partidas)"
                   r" segundo (?:[\d.]+% \((\d+)/(\d+)\)|sin partidas)")


def parse_run(path):
    """[{deck, wr, n, prem, ff, seat1, seat2}] from a saved matrix run."""
    rows, seen = [], set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("==="):
            # The sorted table repeats every deck in a different format; the
            # per-matchup lines above it are the ones carrying the seat split.
            break
        m = _ROW.match(line)
        if not m or m.group("deck") in seen:
            continue
        seen.add(m.group("deck"))
        seat = _SEAT.search(line)
        rows.append({
            "deck": m.group("deck"),
            "wr": float(m.group("wr")) / 100.0,
            "n": int(m.group("n")),
            "prem": float(m.group("prem")) if m.group("prem") else None,
            "ff": int(m.group("ff")),
            "seat1": (int(seat.group(1)), int(seat.group(2))) if seat and seat.group(2) else None,
            "seat2": (int(seat.group(3)), int(seat.group(4))) if seat and seat.group(4) else None,
        })
    return rows


def load_weights(path):
    if not Path(path).exists():
        return None
    with open(path, encoding="utf-8-sig") as fh:
        return {r["archivo"].removesuffix(".csv"): float(r["peso_meta"])
                for r in csv.DictReader(fh)
                if r.get("estado", "admitido") == "admitido"}


def weighted(rows, weights, key=lambda r: r["wr"]):
    """(mean, se, coverage) of `key` weighted by meta share."""
    num = den = var = 0.0
    for r in rows:
        w = weights.get(r["deck"], 0.0)
        if w <= 0:
            continue
        v = key(r)
        if v is None:
            continue
        num += w * v
        den += w
        if r["n"]:
            p = r["wr"]
            var += (w ** 2) * p * (1 - p) / r["n"]
    if not den:
        return None, None, 0.0
    return num / den, math.sqrt(var) / den, den


def seat_rate(rows, weights, which):
    """Weighted winrate in ONE seat: which='seat1' (first) or 'seat2' (second)."""
    num = den = 0.0
    for r in rows:
        w = weights.get(r["deck"], 0.0)
        pair = r[which]
        if w <= 0 or not pair or not pair[1]:
            continue
        num += w * pair[0] / pair[1]
        den += w
    return (num / den if den else None), den


def archetype(deck):
    return deck.rsplit("_", 1)[0]


def by_archetype(rows, weights):
    """{archetype: (weight, weighted winrate, weighted prize, seat gap)}"""
    groups = defaultdict(list)
    for r in rows:
        groups[archetype(r["deck"])].append(r)
    out = {}
    for arch, members in groups.items():
        w_total = sum(weights.get(r["deck"], 0.0) for r in members)
        if w_total <= 0:
            continue
        wr, _se, _c = weighted(members, weights)
        prem, _se2, _c2 = weighted(members, weights, key=lambda r: r["prem"])
        first, _ = seat_rate(members, weights, "seat1")
        second, _ = seat_rate(members, weights, "seat2")
        gap = None if first is None or second is None else first - second
        out[arch] = (w_total, wr, prem, gap)
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", help="saved output of utils/matchup_matrix.py")
    ap.add_argument("--corpus", default=str(_ROOT / "deck" / "real_opponents_500"))
    args = ap.parse_args(argv)

    rows = parse_run(args.run)
    if not rows:
        sys.exit(f"no encontre filas de matchup en {args.run}")
    corpus = Path(args.corpus)
    metas = {}
    for label, name in (("campo", "pesos_campo.csv"), ("top-100", "pesos_top100.csv")):
        w = load_weights(corpus / name)
        if w is None:
            w = load_weights(corpus / "pesos.csv") if label == "campo" else None
        if w:
            metas[label] = w
    if not metas:
        sys.exit(f"no encontre pesos en {corpus}")

    print(f"{len(rows)} matchups leidos de {args.run}")
    ff = sum(r["ff"] for r in rows)
    print(f"forfeits nuestros, total: {ff}")

    print("\n=== WINRATE DE ESCALERA, LAS DOS PONDERACIONES ===")
    for label, w in metas.items():
        wr, se, cov = weighted(rows, w)
        prem, _s, _c = weighted(rows, w, key=lambda r: r["prem"])
        listas = sum(1 for r in rows if w.get(r["deck"], 0) > 0)
        print(f"  {label:8s}: {wr*100:5.2f}% +-{se*196:.2f} "
              f"· premios {prem:+.3f} · {listas} listas con peso "
              f"(cobertura {cov*100:.1f}%)")

    print("\n=== ASIENTO, AGREGADO Y PONDERADO ===")
    print("  (hasta 8192c22 la mitad de 'primero' no se habia ejecutado nunca)")
    for label, w in metas.items():
        first, _d1 = seat_rate(rows, w, "seat1")
        second, _d2 = seat_rate(rows, w, "seat2")
        if first is None or second is None:
            print(f"  {label:8s}: sin division de asiento en este fichero")
            continue
        print(f"  {label:8s}: primero {first*100:5.2f}%  segundo {second*100:5.2f}%"
              f"  diferencia {(first-second)*100:+5.2f} pp")

    if "top-100" in metas:
        print("\n=== DONDE DISCREPAN LAS DOS PONDERACIONES (por arquetipo) ===")
        a_field = by_archetype(rows, metas["campo"])
        a_top = by_archetype(rows, metas["top-100"])
        names = set(a_field) | set(a_top)
        movers = []
        for arch in names:
            wf = a_field.get(arch, (0.0,) * 4)[0]
            wt = a_top.get(arch, (0.0,) * 4)[0]
            movers.append((abs(wt - wf), arch, wf, wt, a_field.get(arch), a_top.get(arch)))
        movers.sort(reverse=True)
        print(f"  {'arquetipo':30s} {'campo':>7s} {'top':>7s} {'delta':>8s} "
              f"{'ganamos':>8s} {'premios':>8s} {'asiento':>9s}")
        for _d, arch, wf, wt, fld, _top in movers[:10]:
            wr = f"{fld[1]*100:.1f}%" if fld and fld[1] is not None else "-"
            pr = f"{fld[2]:+.2f}" if fld and fld[2] is not None else "-"
            gp = f"{fld[3]*100:+.1f}pp" if fld and fld[3] is not None else "-"
            print(f"  {arch:30s} {wf*100:6.2f}% {wt*100:6.2f}% "
                  f"{(wt-wf)*100:+7.2f}pp {wr:>8s} {pr:>8s} {gp:>9s}")

        print("\n=== DONDE SE PIERDEN MAS PUNTOS DE ESCALERA (peso x derrota) ===")
        for label, weights in (("campo", metas["campo"]), ("top-100", metas["top-100"])):
            arcs = by_archetype(rows, weights)
            cost = sorted(((w * (1 - wr), a, w, wr)
                           for a, (w, wr, _p, _g) in arcs.items() if wr is not None),
                          reverse=True)
            top = "  ".join(f"{a} {c*100:.2f}pts" for c, a, _w, _wr in cost[:4])
            print(f"  {label:8s}: {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
