"""Carries a finding across a rebuild of the opponent corpus.

`utils/real_opponents.py` names its output `<archetype>_<n>.csv`, numbered by
descending meta weight WITHIN the archetype. That is the right name while the
meta holds still. It is a trap the moment the leaderboard is re-harvested:
`crustle_wall_6` is not a deck, it is a RANK, and after a rebuild the same rank
lands on a different 60 cards.

This matters because findings are recorded by name. The night of 9-10 August
measured `crustle_wall_6` at 54.5 %, eighteen points below its own family. If
the rebuild silently moves that name onto another list, the morning either
re-measures the wrong deck and calls the finding irreproducible, or measures the
right deck under a name nobody wrote down.

So the bridge matches by CONTENT, never by name:

  * IDENTICAL   -- the same 60 ids, whatever it is called now. The finding
                   transfers with no argument needed.
  * DRIFTED     -- the closest list in the new corpus, with the number of cards
                   that differ. A list at distance 2 is the same deck one week
                   later; a list at distance 30 is a different deck and the
                   match is meaningless. The threshold is printed, not assumed.
  * GONE        -- nothing within the distance limit. The deck left the top 300,
                   and any finding about it can no longer be reproduced against
                   the current meta. That is a result, not a failure.
  * NEW         -- in the new corpus and in no old one. Nothing has ever been
                   measured against these, which is where the unknown is.

Usage:
    python utils/corpus_bridge.py --old deck/real_opponents_2026-08-07 \
                                  --new deck/real_opponents
    python utils/corpus_bridge.py --old ... --new ... --follow crustle_wall_6
    python utils/corpus_bridge.py --old ... --new ... --output log/bridge.md
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Two lists that differ by more than this many cards are not "the same deck a
# week later", they are two decks. 60-card lists of one archetype routinely move
# 2-6 cards between events; past ~12 the shared core stops being an argument.
DEFAULT_LIMIT = 12


def read_deck(path: Path) -> Counter | None:
    """The 60 ids of a deck file, or None if the CSV is not a deck."""
    try:
        tokens = [x for x in path.read_text(encoding="utf-8-sig").split() if x.strip()]
    except (OSError, UnicodeDecodeError):
        return None
    if len(tokens) != 60 or not all(x.lstrip("-").isdigit() for x in tokens):
        return None
    return Counter(int(x) for x in tokens)


def load_folder(folder: Path) -> dict[str, Counter]:
    decks = {}
    for path in sorted(folder.glob("*.csv")):
        deck = read_deck(path)
        if deck is not None:
            decks[path.stem] = deck
    return decks


def distance(a: Counter, b: Counter) -> int:
    """Cards that would have to be swapped to turn one list into the other.

    A multiset difference, not a set one: three copies of a card against one is
    a real difference of two cards, and set logic would call it identical.
    """
    return sum(((a - b) + (b - a)).values())


def closest(deck: Counter, corpus: dict[str, Counter]) -> tuple[str | None, int]:
    best_name, best_distance = None, 10**9
    for name, other in corpus.items():
        d = distance(deck, other)
        if d < best_distance:
            best_name, best_distance = name, d
    return best_name, best_distance


def bridge(old: dict[str, Counter], new: dict[str, Counter], limit: int):
    """One row per old deck, plus the new decks nothing maps onto."""
    rows, claimed = [], set()
    for name, deck in sorted(old.items()):
        match, d = closest(deck, new)
        if match is None:
            rows.append((name, None, None, "GONE"))
            continue
        if d == 0:
            estado = "IDENTICAL"
        elif d <= limit:
            estado = "DRIFTED"
        else:
            estado = "GONE"
        if estado != "GONE":
            claimed.add(match)
            rows.append((name, match, d, estado))
        else:
            rows.append((name, match, d, "GONE"))
    nuevos = sorted(set(new) - claimed)
    return rows, nuevos


def render(rows, nuevos, old_folder, new_folder, limit, follow) -> str:
    out = []
    add = out.append
    add(f"# Corpus bridge: `{old_folder}` -> `{new_folder}`")
    add("")
    add(f"Matched by content. DRIFTED limit: {limit} cards of 60.")
    add("")

    conteo = Counter(estado for _, _, _, estado in rows)
    add(f"| old lists | {len(rows)} |")
    add("|---|---:|")
    for estado in ("IDENTICAL", "DRIFTED", "GONE"):
        add(f"| {estado} | {conteo.get(estado, 0)} |")
    add(f"| NEW (nothing maps onto them) | {len(nuevos)} |")
    add("")

    if follow:
        add(f"## The deck the night was about: `{follow}`")
        add("")
        fila = next((r for r in rows if r[0] == follow), None)
        if fila is None:
            add(f"`{follow}` is not in the old corpus. Nothing to carry.")
        else:
            _, match, d, estado = fila
            if estado == "IDENTICAL":
                add(f"**It survived, and it is now `{match}`.** The same 60 ids. "
                    f"Every finding about `{follow}` transfers to `{match}` "
                    f"with no argument needed"
                    + (" -- and the name did not even move."
                       if match == follow else
                       f" -- but the NAME MOVED, so a command line that still "
                       f"says `{follow}` is measuring a different deck."))
            elif estado == "DRIFTED":
                add(f"**It drifted: closest is `{match}`, {d} cards apart.** "
                    f"Same shell, a week of list-building later. Re-measure "
                    f"before re-using the old number; a {d}-card swap is enough "
                    f"to move a matchup.")
            else:
                add(f"**It is gone from the top 300** (closest is `{match}` at "
                    f"{d} cards, past the {limit} limit). The finding can no "
                    f"longer be reproduced against the current meta. That is an "
                    f"answer: the deck that was beating us left the field.")
        add("")

    add("## Every old list")
    add("")
    add("| old | new | cards apart | |")
    add("|---|---|---:|---|")
    for name, match, d, estado in rows:
        destino = match or "-"
        dist = "-" if d is None else str(d)
        marca = {"IDENTICAL": "same list", "DRIFTED": "drifted",
                 "GONE": "**gone**"}[estado]
        add(f"| `{name}` | `{destino}` | {dist} | {marca} |")
    add("")

    add("## New lists nothing maps onto")
    add("")
    if not nuevos:
        add("None. Every list in the new corpus has an ancestor in the old one.")
    else:
        add(f"{len(nuevos)} lists nothing has ever been measured against:")
        add("")
        for name in nuevos:
            add(f"- `{name}`")
    add("")
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True, help="folder of the previous corpus")
    ap.add_argument("--new", required=True, help="folder of the rebuilt corpus")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"cards apart still called the same deck (default {DEFAULT_LIMIT})")
    ap.add_argument("--follow", default=None,
                    help="the one deck a finding was written about")
    ap.add_argument("--output", default=None, help="markdown file (default: stdout)")
    args = ap.parse_args(argv)

    old_folder, new_folder = Path(args.old), Path(args.new)
    if not old_folder.is_absolute():
        old_folder = ROOT / old_folder
    if not new_folder.is_absolute():
        new_folder = ROOT / new_folder
    for folder in (old_folder, new_folder):
        if not folder.is_dir():
            print(f"ERROR: there is no {folder}", file=sys.stderr)
            return 2

    old, new = load_folder(old_folder), load_folder(new_folder)
    if not old or not new:
        print(f"ERROR: {'old' if not old else 'new'} corpus has no deck",
              file=sys.stderr)
        return 2

    rows, nuevos = bridge(old, new, args.limit)
    texto = render(rows, nuevos, old_folder.name, new_folder.name,
                   args.limit, args.follow)
    if args.output:
        destino = Path(args.output)
        if not destino.is_absolute():
            destino = ROOT / destino
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
        print(f"written to {destino}")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
