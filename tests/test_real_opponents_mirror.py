"""The list that is a copy of OUR OWN list is not a matchup.

The pilotability screen catches the opponent that gets stuck and returns a
falsely high winrate. A near-mirror is the same failure arriving from the other
side: the bot pilots it perfectly legally -- so the screen admits it -- but what
it is piloting is OUR engine, which it plays badly. The winrate comes back at
97% and reads as a matchup we dominate.

The August 2026 corpus carried five of them and one was 60/60 identical to
`deck.csv`, sitting inside `Ogerpon Verde` and dragging that archetype's number
up by a point and a half. They are kept -- somebody really plays them -- and
marked, so the aggregation can report the field with and without.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from real_opponents import MIRROR_OVERLAP, overlap_with


def test_a_list_identical_to_ours_scores_the_whole_deck():
    deck = [1, 1, 1, 2, 3] + list(range(100, 155))
    assert overlap_with(deck, deck) == 60


def test_copies_count_not_just_which_cards():
    """Two lists sharing a staple are not twins.

    Comparing sets would score 4 Ultra Ball against 1 Ultra Ball as a full
    match. What makes a mirror is playing the same NUMBER of copies, so the
    overlap is the sum of the minimum per card.
    """
    cuatro = [7, 7, 7, 7]
    una = [7]
    assert overlap_with(cuatro, una) == 1
    assert overlap_with(una, cuatro) == 1


def test_a_deck_with_nothing_in_common_scores_zero():
    assert overlap_with([1, 2, 3], [4, 5, 6]) == 0


def test_the_threshold_leaves_room_for_a_shared_engine():
    """40/60 is deliberately not 30.

    Two decks of the same archetype legitimately share their engine -- the
    search, the draw Supporters, the basic energy -- and that alone reaches the
    twenties. The measured corpus makes the gap plain: the real opponents
    peaked at 31/60 while every mirror sat at 46 or above, so nothing lands
    near the line.
    """
    assert MIRROR_OVERLAP == 40


def test_the_corpus_marks_its_mirrors():
    """The end-to-end contract, over the corpus actually in the repo.

    Reads pesos.csv, and for every list it claims is a mirror, recomputes the
    overlap from the CSV on disk. A column that stops matching the files is
    exactly how this rots.
    """
    import csv

    import selfplay as sp

    base = ROOT / "deck" / "real_opponents"
    pesos = base / "pesos.csv"
    if not pesos.exists():                       # a fresh checkout has no corpus
        return
    ref = sp.read_deck(str(ROOT / "deck.csv"))
    with pesos.open(encoding="utf-8-sig") as fh:
        filas = list(csv.DictReader(fh))
    assert filas and "solape_propio" in filas[0], "pesos.csv sin la columna"

    for row in filas:
        ruta = base / row["archivo"]
        if not ruta.exists():
            ruta = base / "no_pilotables" / row["archivo"]
        deck = [int(x) for x in ruta.read_text().split() if x.strip().isdigit()]
        assert overlap_with(deck, ref) == int(row["solape_propio"]), row["archivo"]
