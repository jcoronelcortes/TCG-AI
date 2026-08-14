"""The list a RECORDING was played with, for the tests that replay one.

THE PROBLEM
  The agent seeds its whole deck belief from `deck.csv`, read from the process's
  working directory at import time (`main.py:165`). That is right for a live
  game -- the sixty cards it is playing are the sixty cards on disk -- and wrong
  for a replay: `records/`, `tests/fixtures/` and the frozen corpus hold boards
  played with the list of their day, and today's `deck.csv` is a different sixty.

  What goes wrong is not cosmetic. `_reconciliar_desde_vista_mazo`
  (`ptcg/state/tracking.py`) files a copy as PRIZED when the deck view does not
  show it and the current list says it exists:

      hidden = total_copies - HAND - BENCH - DISCARD      # total_copies <- deck.csv
      PRIZE  = hidden - (copies visible in the deck view)

  So every copy the CURRENT list holds and the recorded one did not is filed,
  silently, as a prize. On 13 August 2026 the list gained a Poke Pad and a Basic
  {G} Energy, and the belief started placing SEVEN cards in six prizes on
  recorded boards. That impossible state then wakes the in-flight arbiter, which
  moves a copy out of the prizes on the premise that the searcher is on its way
  to the discard -- true of an Item being played, false of an ability used by a
  body that stays on the bench.

  The visible damage is a rule reading a belief nobody's game produced. In
  `test_ld_committed_supporter` it flipped `do_not_shuffle_the_last_xerosic`:
  the record's deck view reveals all 41 remaining cards with no Meowth ex among
  them, so the second copy is provably PRIZED, and only the recorded list gets
  that answer.

THE RULE
  A test that replays a recording states the list of the recording. It is not a
  courtesy to the past: it is the only list under which the assertions of that
  test are about the agent rather than about the difference between two decks.

      from recorded_deck import deck_of_record

      with deck_of_record():          # the list of before 14 August 2026
          hecho = _reproducir(_observaciones())

WHAT IT SWAPS, AND WHAT IT DOES NOT
  `main.my_deck` and the belief seeded from it (`_init_cards_tracking`). It does
  NOT rebuild `_DECK_CHAINS` / `_DECK_POKEMON_IDS`, which are computed at import
  from the evolution lines of the list: both lists hold the same lines and
  differ only in COUNTS, so nothing downstream of them moves. A future list that
  adds or drops a whole line needs more than this helper, and it should fail
  loudly rather than be extended quietly.

See [[el-corpus-grabado-es-de-la-lista-vieja]].
"""

from contextlib import contextmanager
from pathlib import Path

from patching import instalar

ROOT = Path(__file__).resolve().parents[1]

#: The list every recording before 14 August 2026 was played with:
#: 2 Tapu Bulu, 2 Night Stretcher, 1 Poke Pad, 13 Basic {G} Energy.
PRE_2026_08_14 = ROOT / "tests" / "fixtures" / "deck_2026-08-13.csv"


def read_list(path=PRE_2026_08_14):
    """The 60 ids of a list file, in order, with its size asserted here.

    A list that is not sixty cards is a broken fixture and it is worth saying so
    at the point of reading: the belief built from it would be wrong in a way
    that only shows up several rules later.
    """
    ids = [int(line) for line in Path(path).read_text().split("\n") if line.strip()]
    if len(ids) != 60:
        raise ValueError(f"{path}: {len(ids)} cards, a list is 60")
    return ids


@contextmanager
def deck_of_record(path=PRE_2026_08_14):
    """Replays under the list of the recording, and restores the current one."""
    import main as m

    restore = instalar("my_deck", read_list(path))
    m._init_cards_tracking()
    try:
        yield
    finally:
        restore()
        m._init_cards_tracking()
