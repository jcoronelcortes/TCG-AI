"""The flip-diff, on a machine that has never played a game.

T3.4 of docs/testing-plan-2026-08.md, and the half of the golden corpus that was
missing. `tests/test_golden_corpus.py` replays `records/`, which is git-ignored
transient data, so on a clean checkout it SKIPS -- and the CI workflow says so in
its own header: "the corpus is exercised here only as far as a clean checkout
allows". Which is to say: not at all, in exactly the situation where a reviewer
most wants to know which historical decisions a change flipped.

`tests/corpus/` closes that. The same fifty games, with only OUR decisions kept,
gzip to 0.85 MB -- so there is no sampling and no argument about which games are
representative: all of them are in.

THE TWO CORPORA ARE NOT REDUNDANT, and the difference is the point.

  * the LOCAL one self-heals. Records are transient, so a record with a
    different md5 re-snapshots silently and only a flip on an UNTOUCHED record
    fails. That is right for data that is regenerated whenever new games are
    analysed;
  * the FROZEN one cannot self-heal. It is versioned by git, so its snapshot
    only changes when somebody commits a change to it, and every flip is a flip.
    That is what makes it usable as a gate rather than as a notebook.

WHEN THIS FAILS, it is not asking to be silenced. It has found that a change to
the agent altered decisions on 3 580 recorded boards, and it prints which ones.
If the change was intended -- as it is for most rule work -- the flips are
reviewed and then:

    python utils/freeze_corpus.py --snapshot-only

re-plays the committed bundle and rewrites its snapshot, and the diff of that
commit is the record of what was accepted, which is the artefact worth having.

The flag matters. Without it the tool also REBUILDS the bundle out of
`records/`, which is transient and git-ignored: a working tree usually holds a
handful of games while the bundle holds every game somebody ever froze, so
accepting a flip that way silently shrinks the gate -- and the bundle is a
gzip, so the commit diff does not show it. `freeze_corpus.py` now refuses to
shrink without `--force`; use the plain form only after
`utils/record_corpus.py --games 50` has refilled `records/`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import golden_corpus as gc  # noqa: E402

# What the bundle was frozen with. A floor rather than an equality: adding games
# is good and should not need this file edited, losing them silently is not.
MINIMUM_RECORDS = 40
MINIMUM_DECISIONS = 3000


def test_the_frozen_corpus_is_committed_and_is_not_empty():
    """The guard that stops every test below from passing vacuously.

    An absent bundle would make the comparison compare nothing, which is the
    failure mode the local corpus already documents: an empty list compares
    equal to an empty list forever.
    """
    assert gc.FROZEN_BUNDLE.exists(), (
        f"falta {gc.FROZEN_BUNDLE.relative_to(ROOT)}; "
        f"generalo con python utils/freeze_corpus.py")
    assert gc.FROZEN_SNAPSHOT.exists(), (
        f"falta {gc.FROZEN_SNAPSHOT.relative_to(ROOT)}")
    frozen = gc.frozen_records()
    assert len(frozen) >= MINIMUM_RECORDS, (
        f"solo {len(frozen)} registros congelados, se esperaban "
        f">= {MINIMUM_RECORDS}")
    decisions = sum(len(r["steps"]) for r in frozen.values())
    assert decisions >= MINIMUM_DECISIONS, (
        f"solo {decisions} decisiones congeladas")


def test_every_frozen_record_carries_its_seat():
    """`our_index` cannot be trusted on a one-seat bundle, so the seat is stored.

    It votes by counting how many visible cards of EACH seat come from deck.csv,
    and the bundle deliberately keeps only the observations of one of them. The
    seat is written at freeze time, when the whole stream is still there.
    """
    for name, record in gc.frozen_records().items():
        assert record.get("seat") in (0, 1), f"{name} sin asiento"


def test_no_historical_decision_has_flipped():
    """The flip-diff itself, on a clean checkout."""
    frozen = gc.frozen_records()
    module = gc._main_mod()
    actual = {name: {"decisiones": gc.replay_data(module, data)}
              for name, data in sorted(frozen.items())}
    stored = gc.load_frozen_snapshot()

    # UNPACKED, and the first version was not: `comparar` returns a 4-tuple of
    # lists, and a tuple of four empty lists is TRUTHY. `if flips:` fired on a
    # corpus with nothing wrong with it, which is the same shape of bug this
    # week has been full of -- a detector reporting itself.
    changed, missing, added, flips = gc.comparar(stored, actual)
    problems = []
    if flips:
        problems.append("decisiones que cambiaron:\n" + gc.formatear_flips(flips))
    if changed:
        problems.append(f"registros con otro contenido: {changed}")
    if missing:
        problems.append(f"registros del snapshot que ya no estan: {missing}")
    if added:
        problems.append(f"registros sin entrada en el snapshot: {added}")
    if problems:
        pytest.fail(
            "el corpus congelado ya no dice lo mismo:\n" + "\n".join(problems)
            + "\n\nSi el cambio es intencionado, revisa los flips y luego:"
              "\n    python utils/freeze_corpus.py --snapshot-only")
