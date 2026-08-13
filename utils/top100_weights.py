"""Re-weights an opponents corpus by the TOP of the leaderboard, not by the field.

Why this exists. `utils/real_opponents.py` gives each admitted list the weight it
has in the WHOLE downloaded corpus. Measured on the 500-deck sweep (12 Aug 2026),
that hides something: the top of the ladder is a different meta from the rest of
it.

    positions   1-100 : Marnie 21 %, Lopunny/Froslass 16 %, Alakazam 15 %, Dragapult 14 %
    positions 401-500 : Marnie 42 %, Alakazam 14 %, Crustle 13 %, Dragapult  5 %

With 400 of the 500 rows below position 100, a field-weighted average quietly
answers "how well do I beat the players I already outrank". The decks that WIN
are not the decks the field PLAYS, so a run that wants to say something about
climbing needs the second weighting too.

It writes three files next to the corpus, and the third one is the subtle one:

  * `pesos_top100.csv`  the weight of each admitted list among positions 1..N only.
    Lists with no deck in that band get weight 0 -- kept, not dropped, so the
    matrix never has to guess what a missing row means.
  * `pesos_campo.csv`   a copy of the field weights, so both weightings sit side
    by side and a report can never be ambiguous about which one it used.
  * `pesos_alloc.csv`   max(field, top100) per list, renormalised. This one is
    NOT a meta model and must never be used as a summary: it exists to spread
    `--allocation peso`'s game budget so that BOTH summaries rest on an adequate
    sample. Allocating by field weight alone under-samples exactly the lists the
    top-100 summary leans on, and the top-100 number then arrives with an
    interval too wide to say anything.

The admitted lists are matched back to their source decks by CONTENT (the sorted
60 ids), not by filename: `real_opponents.py` renames and renumbers as it
deduplicates, so the filename carries no reliable link back to a leaderboard
position.

Usage:
    python utils/top100_weights.py
    python utils/top100_weights.py --top 100 --corpus deck/real_opponents_500
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def load_ids(path):
    """The deck as a sorted tuple of 60 ids -- the identity used to match."""
    with open(path, encoding="utf-8-sig") as fh:
        return tuple(sorted(int(line) for line in fh if line.strip()))


def source_positions(decks_dir):
    """{deck identity: [leaderboard positions]} for the downloaded corpus."""
    index = decks_dir / "indice.csv"
    if not index.exists():
        sys.exit(f"no encuentro {index}")
    out = {}
    with open(index, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            ids = load_ids(decks_dir / row["archivo"])
            out.setdefault(ids, []).append(int(row["posicion_leaderboard"]))
    return out


def admitted_lists(corpus_dir):
    """[(filename, archetype, identity)] for every admitted list of the corpus."""
    out = []
    for path in sorted(corpus_dir.glob("*.csv")):
        if path.name.startswith("pesos"):
            continue
        archetype = path.stem.rsplit("_", 1)[0].replace("_", " ")
        out.append((path.name, archetype, load_ids(path)))
    return out


def write_weights(path, rows, column):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["archivo", "arquetipo", column, "mazos_origen"])
        for name, archetype, weight, sources in rows:
            writer.writerow([name, archetype, f"{weight:.6f}", sources])


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decks", default=str(_ROOT / "competitor_decks_500"),
                    help="downloaded corpus with indice.csv")
    ap.add_argument("--corpus", default=str(_ROOT / "deck" / "real_opponents_500"),
                    help="opponents corpus produced by real_opponents.py")
    ap.add_argument("--top", type=int, default=100,
                    help="size of the top band (default 100)")
    args = ap.parse_args(argv)

    decks_dir, corpus_dir = Path(args.decks), Path(args.corpus)
    positions = source_positions(decks_dir)
    lists = admitted_lists(corpus_dir)
    if not lists:
        sys.exit(f"{corpus_dir} no tiene listas admitidas todavia")

    # Field and top-band deck counts per admitted list. A list whose identity is
    # absent from the source corpus is a real error, not a zero: it would mean the
    # corpus was built from a different download.
    field, top = Counter(), Counter()
    for name, _archetype, ids in lists:
        if ids not in positions:
            sys.exit(f"{name} no aparece en {decks_dir}: corpus descolgado")
        pos = positions[ids]
        field[name] = len(pos)
        top[name] = sum(1 for p in pos if p <= args.top)

    total_field, total_top = sum(field.values()), sum(top.values())
    if not total_top:
        sys.exit(f"ninguna lista admitida aparece en el top-{args.top}")

    rows_field, rows_top, rows_alloc = [], [], []
    raw_alloc = {}
    for name, archetype, _ids in lists:
        w_field = field[name] / total_field
        w_top = top[name] / total_top
        rows_field.append((name, archetype, w_field, field[name]))
        rows_top.append((name, archetype, w_top, top[name]))
        raw_alloc[name] = max(w_field, w_top)

    total_alloc = sum(raw_alloc.values())
    for name, archetype, _ids in lists:
        rows_alloc.append((name, archetype, raw_alloc[name] / total_alloc,
                           field[name]))

    write_weights(corpus_dir / "pesos_campo.csv", rows_field, "peso_meta")
    write_weights(corpus_dir / "pesos_top100.csv", rows_top, "peso_meta")
    write_weights(corpus_dir / "pesos_alloc.csv", rows_alloc, "peso_meta")

    print(f"{len(lists)} listas admitidas · {total_field} mazos del campo · "
          f"{total_top} en el top-{args.top}")
    print(f"escritos: pesos_campo.csv, pesos_top100.csv, pesos_alloc.csv "
          f"en {corpus_dir}")

    # The movers ARE the result: the rows where the two weightings disagree most
    # are the first draft of what a playbook should prioritise.
    movers = sorted(((abs(t - f), n, a, f, t)
                     for (n, a, f, _s), (_n2, _a2, t, _s2)
                     in zip(rows_field, rows_top)),
                    reverse=True)
    print(f"\nDonde mas discrepan las dos ponderaciones (campo -> top-{args.top}):")
    print(f"  {'lista':32s} {'campo':>8s} {'top':>8s}  {'delta':>8s}")
    for _d, name, _arch, w_field, w_top in movers[:12]:
        print(f"  {name:32s} {w_field*100:7.2f}% {w_top*100:7.2f}% "
              f"{(w_top-w_field)*100:+7.2f}pp")

    absent = [n for _d, n, _a, _f, t in movers if t == 0]
    if absent:
        print(f"\n{len(absent)} listas admitidas NO aparecen en el top-{args.top} "
              f"(peso 0, conservadas): {', '.join(absent[:6])}"
              + (" ..." if len(absent) > 6 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
