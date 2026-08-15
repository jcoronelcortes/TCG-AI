"""Tests of autopsy v2 (step 5 of the jul 2026 plan): the loss MODE
classifier. The prize convention is the one used in the rest of utils/autopsy.py: a
None entry in prize is a prize that player has STILL to take."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from autopsy import classify_loss


def _obs_final(op_prizes_left, my_active, my_bench, mi_deck):
    """A minimal terminal observation for the classifier (seat 0)."""
    yo = {
        "active": [my_active] if my_active else [None],
        "bench": my_bench,
        "deckCount": mi_deck,
        "prize": [None] * 6,
    }
    op = {
        "active": [{"id": 37}],
        "bench": [],
        "deckCount": 30,
        "prize": [None] * op_prizes_left + [{"id": 1}] * (6 - op_prizes_left),
    }
    return {"current": {"players": [yo, op], "yourIndex": 0, "result": 1}}


def test_loss_on_prizes():
    obs = _obs_final(op_prizes_left=0,
                     my_active={"id": 920}, my_bench=[{"id": 92}], mi_deck=20)
    assert classify_loss(obs, seat=0, result="pierde") == "premios"


def test_loss_by_bench_out():
    # The opponent still had prizes pending: the cause is running out of Pokemon.
    obs = _obs_final(op_prizes_left=3,
                     my_active=None, my_bench=[None, None], mi_deck=20)
    assert classify_loss(obs, seat=0, result="pierde") == "bench_out"


def test_loss_by_deckout():
    obs = _obs_final(op_prizes_left=3,
                     my_active={"id": 920}, my_bench=[], mi_deck=0)
    assert classify_loss(obs, seat=0, result="pierde") == "deckout"


def test_bench_out_gana_a_deckout():
    # An empty board AND the deck at 0 with prizes pending: the KO that swept the
    # board is the proximate cause.
    obs = _obs_final(op_prizes_left=1,
                     my_active=None, my_bench=[], mi_deck=0)
    assert classify_loss(obs, seat=0, result="pierde") == "bench_out"


def test_prizes_dominates_deckout():
    # The opponent completed their prizes in a game that also left us at 0
    # deck: the loss is on prizes (the deck-out never got to happen).
    obs = _obs_final(op_prizes_left=0,
                     my_active={"id": 920}, my_bench=[], mi_deck=0)
    assert classify_loss(obs, seat=0, result="pierde") == "premios"


def test_the_boundary_is_classified_outright():
    obs = _obs_final(op_prizes_left=2,
                     my_active={"id": 920}, my_bench=[], mi_deck=10)
    assert classify_loss(obs, seat=0, result="limite") == "limite"


def test_a_broken_observation_does_not_raise():
    assert classify_loss({}, seat=0, result="pierde") == "desconocido"
    assert classify_loss(None, seat=0, result="pierde") == "desconocido"


# ---------------------------------------------------------------------------
# The boundary between the tool that WRITES the finding and the one that READS it
# ---------------------------------------------------------------------------

def test_the_finding_carries_the_key_the_explorer_reads():
    """`utils/turn_explorer.py` has to be able to read what autopsy writes.

    The key travels in JSON between two tools, so no test of either one alone
    crosses that boundary -- and the Spanish->English rename walked straight
    through the gap: the reader was changed to `turn` while every writer
    (autopsy, shadow, the golden corpus) and the 900+ files already in
    `records/` kept `turno`. The tool did not fail a test, it crashed with a
    KeyError on the first real finding, which is a documented step of the
    improvement loop silently unavailable.

    This pins the contract from the reader's side: whatever the writers emit,
    the explorer resolves a turn out of it without raising.
    """
    import turn_explorer

    written = {"detector": "turno_esteril", "turno": 7, "detalle": "END",
               "observation": {}}
    assert turn_explorer.turn_of(written) == 7

    # A record written by a future English writer stays readable.
    assert turn_explorer.turn_of({"turn": 7}) == 7
    # And a record with neither degrades instead of crashing.
    assert turn_explorer.turn_of({}) == "?"


# ---------------------------------------------------------------------------
# THE HALF `letal_perdido` DID NOT ASK: what taking the knockout COSTS
# ---------------------------------------------------------------------------

def _obs_lethal(their_prizes_left, our_active, their_active, our_bench=()):
    """A MAIN-menu observation for `_ko_hands_them_the_game` (seat 0)."""
    yo = {
        "active": [our_active], "bench": list(our_bench),
        "deckCount": 20, "handCount": 3, "hand": [],
        "prize": [None] * 5,
    }
    op = {
        "active": [their_active], "bench": [],
        "deckCount": 20, "handCount": 3, "hand": [],
        "prize": [None] * their_prizes_left,
    }
    return {"current": {"players": [yo, op], "yourIndex": 0, "turn": 24}}


def _pk(cid, hp, maxhp, energies=0):
    return {"id": cid, "hp": hp, "maxHp": maxhp,
            "energies": [1] * energies,
            "energyCards": [{"id": 1}] * energies, "tools": []}


def test_the_lethal_that_hands_them_the_game_is_marked():
    """Game 275 vs mega_lopunny_mega_froslass_1, turn 24, in miniature.

    Their pile is at TWO and our active is an ex: the knockout is real and
    taking it from the front closes THEIR count, not ours. The agent declines
    it on purpose (`PROMO_MATCH_POINT_VETO`), so the detector must not file the
    board under "missed prize" without saying what it would have cost.
    """
    import main as m
    from autopsy import _ko_hands_them_the_game

    obs = _obs_lethal(
        their_prizes_left=2,
        our_active=_pk(m.Teal_Mask_Ogerpon_ex, 50, 210, energies=3),
        their_active=_pk(849, 180, 330, energies=2))          # Mega Lopunny ex
    assert _ko_hands_them_the_game(m, obs) is True


def test_the_same_lethal_with_their_pile_out_of_reach_is_not_marked():
    """The boundary, and it is the one that keeps the reading honest: the same
    board with their pile at THREE. Two prizes no longer close their count, so
    the knockout costs nothing that the detector may charge it for."""
    import main as m
    from autopsy import _ko_hands_them_the_game

    obs = _obs_lethal(
        their_prizes_left=3,
        our_active=_pk(m.Teal_Mask_Ogerpon_ex, 50, 210, energies=3),
        their_active=_pk(849, 180, 330, energies=2))
    assert _ko_hands_them_the_game(m, obs) is False


def test_a_one_prize_body_in_front_is_not_marked():
    """A body worth ONE prize does not close a pile of two, whatever their
    active does to it."""
    import main as m
    from autopsy import _ko_hands_them_the_game

    obs = _obs_lethal(
        their_prizes_left=2,
        our_active=_pk(m.Meganium, 30, 150, energies=4),
        their_active=_pk(849, 180, 330, energies=2))
    assert _ko_hands_them_the_game(m, obs) is False
