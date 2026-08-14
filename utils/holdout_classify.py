"""Which archetypes do the 370 unlabelled extras belong to?

`competitor_decks_500/adicionales/` holds lists harvested with the 500 but
carrying no leaderboard position and no archetype label. They are the honest
test of anything fitted to the 500: a recommendation derived from the corpus we
measured, that does not survive here, is fitted to those exact lists rather than
to the meta.

Tonight's use is deliberately minimal -- CLASSIFY ONLY. Each extra is labelled
by nearest neighbour among the admitted corpus lists, counting copies
(`real_opponents.overlap_with`), and anything whose best match is weak is
reported `desconocido` rather than forced into the closest bucket. The point of
the exercise is the tail: how much of this set is something the 500 never
showed us.

The floor is the corpus's own separation, not a taste: two lists of the same
archetype legitimately share their engine and land in the twenties, so 40/60 --
the same MIRROR_OVERLAP the mirror screen uses -- is where a claim of "the same
deck" starts.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from real_opponents import MIRROR_OVERLAP, overlap_with  # noqa: E402


def read_list(path):
    return [int(x) for x in Path(path).read_text().split() if x.strip().isdigit()]


def reference_lists(corpus):
    """(name, archetype, ids) for every admitted list of the corpus."""
    weights = Path(corpus) / "pesos.csv"
    out = []
    with weights.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row.get("estado") != "admitido":
                continue
            path = Path(corpus) / row["archivo"]
            if path.exists():
                out.append((row["archivo"], row["arquetipo"], read_list(path)))
    return out


def classify(deck, refs, floor):
    best_name, best_arch, best = "", "desconocido", -1
    for name, arch, ids in refs:
        score = overlap_with(deck, ids)
        if score > best:
            best_name, best_arch, best = name, arch, score
    if best < floor:
        return "desconocido", best_name, best
    return best_arch, best_name, best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--extras", default=str(_ROOT / "competitor_decks_500" / "adicionales"))
    ap.add_argument("--corpus", default=str(_ROOT / "deck" / "real_opponents_500"))
    ap.add_argument("--floor", type=int, default=MIRROR_OVERLAP,
                    help=f"overlap below which the answer is 'desconocido' (default {MIRROR_OVERLAP})")
    ap.add_argument("--out", default=None, help="CSV of one row per extra")
    args = ap.parse_args(argv)

    refs = reference_lists(args.corpus)
    if not refs:
        print(f"ERROR: no admitted list in {args.corpus}", file=sys.stderr)
        return 1
    paths = sorted(Path(args.extras).glob("*.csv"))
    if not paths:
        print(f"ERROR: no list in {args.extras}", file=sys.stderr)
        return 1

    rows, tally, unknown = [], Counter(), []
    sizes = Counter()
    for path in paths:
        deck = read_list(path)
        sizes[len(deck)] += 1
        if len(deck) != 60:
            unknown.append((path.name, "no son 60 cartas", len(deck)))
            continue
        arch, near, score = classify(deck, refs, args.floor)
        tally[arch] += 1
        rows.append({"archivo": path.name, "arquetipo": arch,
                     "vecino": near, "solape": score})

    print(f"{len(paths)} extras, {len(refs)} listas de referencia, "
          f"suelo {args.floor}/60")
    if sizes and set(sizes) != {60}:
        print(f"  tamanos: {dict(sizes)}")
    print()
    for arch, n in tally.most_common():
        marca = "  <- fuera del corpus" if arch == "desconocido" else ""
        print(f"  {arch:<34} {n:>4}  ({100 * n / max(1, len(rows)):4.1f}%){marca}")

    desconocidos = [r for r in rows if r["arquetipo"] == "desconocido"]
    if desconocidos:
        print(f"\nLos {len(desconocidos)} desconocidos, por su mejor vecino "
              f"(ninguno llega al suelo):")
        for r in sorted(desconocidos, key=lambda r: -r["solape"])[:15]:
            print(f"  {r['archivo']:<16} mejor {r['vecino']:<30} {r['solape']}/60")

    if args.out:
        with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["archivo", "arquetipo", "vecino", "solape"])
            w.writeheader()
            w.writerows(rows)
        print(f"\nFilas en {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
