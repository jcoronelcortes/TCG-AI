"""The Stamp's ladder prices the evolutions the hand can really make TODAY.

`_RULES_STAMP_PLAY` prices the Unfair Stamp by what ELSE the hand can do this
turn -- "the base value rises the LESS alternative use the hand has this turn":

    Pokemon/evo playable  2000  <  item  2500  <  energy/stadium  3000  <  nothing  7500

`_us_evo_jugable` answered the "evo" rung with a raw hand/field census and no
legality filter, so a pre-evolution that had ALREADY EVOLVED this turn still
counted as an evolution the hand could make, pinning the Stamp to its lowest
rung.

Record (user, episode 90587542 step 150, turn 16 vs Hop's, LOST): the Dipplin
had evolved from an Applin on step 141 (`appearThisTurn: true`) and the bench
was full at 5, so the menu offered NO evolution and no Pokemon play at all --
and the two Hydrapple ex in hand still priced the Stamp at 2000. It is the same
shape as registro_006 step 84, the record that made `_evolvable_counts` exist.

The fix counts through that primitive (present NOW *and* present when the turn
started, with Forest of Vitality lifting the restriction), the same criterion
`_ub_evolve_now_search` and `_lillie_evolve_now` already spelled out by hand.

IT IS A CORRECTNESS FIX, NOT A WINRATE ONE, and the record is where that is
clearest: it lifts step 150's Stamp from 2200 to 2700 -- still far below the
8600 snipe, so on its own it would NOT have changed that decision. What changed
it is the ORDER net (`test_the_ko_window_dies_with_the_attack.py`). Measured in
`log/census_gate/`: the census disagreed on 31 of 707 priced boards (4.4%), all
31 moving the rung, for ~2 flipped decisions in 1600 games and 0 golden-corpus
flips.

Coverage:
  * the record's board: the rung is the ITEM one, not the Pokemon/evo one, and
    the decision is unchanged;
  * the predicate itself, on the four cases that decide it -- evolved today,
    still there since the turn started, under Forest, and on the turn's first
    menu (empty snapshot = no data, the current field rules);
  * the control: a body that WAS there at the start still lowers the rung, so
    the fix only ever SUBTRACTS a phantom.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

import main as m
from patching import instalar

STAMP = m.Unfair_Stamp
HYDRAPPLE = m.Hydrapple_ex
DIPPLIN = m.Dipplin
APPLIN = m.Applin

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "hops_step150_the_stamp_goes_before_the_attack.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return (copy.deepcopy(data["previous_observation"]),
            copy.deepcopy(data["observation"]))


def _decision():
    """Replays step 150 and returns (choice, the Stamp's score)."""
    previous, dec = _load()
    seen = {}
    original = m._score_unfair_stamp_play

    def spy(ctx):
        seen["stamp"] = original(ctx)
        return seen["stamp"]

    restore = instalar("_score_unfair_stamp_play", spy)
    try:
        m.agent(previous)
        choice = m.agent(dec)
    finally:
        restore()
    return choice, seen.get("stamp"), dec


def _ctx(field, at_start, *, forest=False, hand=None):
    return SimpleNamespace(hand_counts=hand or {HYDRAPPLE: 2},
                           field_counts=field,
                           field_at_turn_start=at_start,
                           forest_in_play=forest,
                           meganium_in_play=False)


# ---------------------------------------------------------------------------
# 1. The record's board
# ---------------------------------------------------------------------------

def test_step150_the_board_has_no_evolution_to_make():
    """Without this the test measures nothing: the phantom evolution is a
    Dipplin that evolved THIS turn, on a bench with no room either."""
    _, dec = _load()
    cur = dec["current"]
    mine = cur["players"][cur["yourIndex"]]

    dipplin = [p for p in mine["bench"] if p["id"] == DIPPLIN]
    assert len(dipplin) == 1 and dipplin[0]["appearThisTurn"] is True, (
        "the Dipplin evolved on step 141: it cannot evolve again this turn")
    assert len(mine["bench"]) == mine["benchMax"], "no room to play a Pokemon"
    assert [c["id"] for c in mine["hand"]].count(HYDRAPPLE) == 2, (
        "the two Hydrapple ex are what the census read as a live evolution")
    assert not any(o["type"] in (int(m.OptionType.EVOLVE),)
                   for o in dec["select"]["option"]), (
        "the engine itself offers no evolution")


def test_step150_the_stamp_is_priced_on_the_item_rung():
    _, score, _ = _decision()
    # 2500 (item: the two Ultra Balls) + 200 (`we_are_losing_on_prizes`),
    # instead of 2000 + 200 for an evolution that cannot be made.
    assert score == 2700, (
        f"the Stamp should leave the Pokemon/evo rung; scored {score}")


def test_step150_the_decision_does_not_change():
    """The ladder gets truthful, not louder: 2700 is still far below the 8600
    snipe, so what puts the Stamp ahead is the ORDER net, not this."""
    choice, _, dec = _decision()
    cur = dec["current"]
    mine = cur["players"][cur["yourIndex"]]
    opt = dec["select"]["option"][choice[0]]
    assert opt["type"] == int(m.OptionType.PLAY)
    assert mine["hand"][opt["index"]]["id"] == STAMP


# ---------------------------------------------------------------------------
# 2. The predicate, on the four cases that decide it
# ---------------------------------------------------------------------------

def test_a_body_that_evolved_today_is_not_an_evolution():
    """The record's shape: a Dipplin on the field that was not there when the
    turn started, because it WAS the Applin."""
    assert m._us_evo_jugable(
        _ctx({DIPPLIN: 1}, {APPLIN: 1})) is False


def test_a_body_that_was_already_there_still_is_one():
    """The control. The fix only ever SUBTRACTS a phantom: with the Dipplin
    present since the turn started, the rung stays where it was."""
    assert m._us_evo_jugable(
        _ctx({DIPPLIN: 1}, {DIPPLIN: 1})) is True


def test_under_forest_of_vitality_the_restriction_lifts():
    """Forest of Vitality removes the "it came down this turn" restriction, so
    the CURRENT field rules -- `_evolvable_counts` already says so and the
    census inherits it."""
    assert m._us_evo_jugable(
        _ctx({DIPPLIN: 1}, {APPLIN: 1}, forest=True)) is True


def test_on_the_first_menu_of_the_turn_the_current_field_rules():
    """An empty snapshot is NO DATA, not "nothing was there": it is the state
    before the turn's photo is taken, and there the current field rules."""
    assert m._us_evo_jugable(_ctx({DIPPLIN: 1}, {})) is True


def test_the_whole_line_is_filtered_not_just_the_hydrapple():
    """The four branches read the same census, so the filter reaches all of
    them: a Chikorita that came down this turn is not a Bayleef either."""
    assert m._us_evo_jugable(
        _ctx({m.Chikorita: 1}, {}, hand={m.Bayleef: 1})) is True
    assert m._us_evo_jugable(
        _ctx({m.Chikorita: 1}, {m.Applin: 1}, hand={m.Bayleef: 1})) is False
