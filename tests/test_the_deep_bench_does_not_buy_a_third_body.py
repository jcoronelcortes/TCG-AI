"""A bench that already carries two bodies is not worth two cards of hand.

Second deck for the two rules of
tests/test_ultra_ball_does_not_buy_a_bench_slot_with_tomorrow.py (Marnie,
episode 90088766). Nothing is changed here: this file exists because both rules
are read off the SHAPE OF THE BOARD -- how deep the bench is, whether the turn's
Supporter is already spent -- and off no matchup at all, so a second archetype
with a different hand has to reach the same decision. It did not: at HEAD this
record repeats the Marnie mistake card for card.

Scenario (`records/registro_002_pasos_007_hasta_022.json`, step 18, turn 2,
episode 90109386 vs Alakazam -- LOST):

    US (6 prizes)                             RIVAL (Alakazam)
    active  Fezandipiti ex 210, 1 {G}         active  Abra 50
    bench   Teal Mask Ogerpon ex 210, 1 {G}   bench   Shaymin 80
            Teal Mask Ogerpon ex 210, 1 {G}   (both of ours fresh)
    hand    **Lillie's Determination**, Hydrapple ex x2, **Ultra Ball**
    turn's Supporter: ALREADY SPENT (a Lillie's, step 9)
    menu:   PLAY Ultra Ball / RETREAT / END      <- there is NO attack

The turn's Supporter was spent, a first Ultra Ball had already bought the
SECOND body of the bench (a bench of one: that one is the rule working, and the
control below pins it), and the draw handed a second Ultra Ball plus the second
Lillie's -- the card that restarts the hand next turn, and the only one, with
the turn's slot already gone. The agent played it, paid the two discards with a
Hydrapple ex AND that Lillie's, and fetched a Chikorita: a 70 HP body for a
bench that already had two, on a turn with no attack, from a hand whose two
Hydrapple ex have no Applin and no Dipplin anywhere to evolve from.

`_score_ultra_ball_play` scored it **-1** on this board -- the base scorer never
wanted it. The play came out of the STERILE-TURN NET alone, which lifted it to
200 because `_st_basic_useful` only asked for a bench with room and a basic in
the deck. What keeps it down now is rule 1 (`bench_count <= 1`,
ptcg/turn/finalize.py): the only reasons to pay two cards for an Ultra Ball are
to be able to ATTACK, or to stop being one knockout away from having no bodies,
and this net only fires on turns with no attack, so what is left is bench depth.
The cost counterfactual is rule 2 (`_protect_refresh_supporter`,
ptcg/turn/options/card.py): a lone refill Supporter is protected BECAUSE the
turn's Supporter is spent, which is exactly when nothing can compete for the
next turn's slot.

The two rules are the ones already measured on the Marnie record (golden corpus
2 flips; shadow of two trees, 200 mirror games / 24304 decisions: 51 flips =
0.21%, all in the intended direction; head-to-head n=1000 neutral). This board
adds no rule and moves no threshold, so it is pinned, not re-measured.

Not fixed here, and deliberately: `_ub_real_fodder` still counts a refill
Supporter as fodder once the turn's Supporter is spent -- on this board it
returns 3, so no COST veto fires and the whole wall is rule 1. Mirroring rule 2
there was tried and it killed three measured counter-examples (see the Marnie
file); the over-count only ever allows more Ultra Balls, which is the
conservative side of the seam.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_STEP18 = ROOT / "tests" / "fixtures" / (
    "alakazam_t2_ultra_ball_does_not_fill_the_bench_step18.json")
_STEP19 = ROOT / "tests" / "fixtures" / (
    "alakazam_t2_ultra_ball_cost_step19.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m._field_at_turn_start = {}
    yield
    m._init_cards_tracking()


def _obs(path):
    return copy.deepcopy(json.load(open(path, encoding="utf-8"))["observation"])


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _chosen(obs):
    return obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]


def _discarded_ids(obs):
    hand = _mine(obs)["hand"]
    return sorted(hand[obs["select"]["option"][i]["index"]]["id"]
                  for i in m.agent(copy.deepcopy(obs)))


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_sterile_turn_2_with_the_supporter_spent():
    obs = _obs(_STEP18)
    cur = obs["current"]
    mine = _mine(obs)

    assert cur["turn"] == 2 and cur["supporterPlayed"]
    # No attack in the menu: the turn IS sterile, which is what wakes the net.
    types = [o["type"] for o in obs["select"]["option"]]
    assert int(m.OptionType.ATTACK) not in types
    assert int(m.OptionType.END) in types

    assert [c["id"] for c in mine["hand"]] == [
        m.Lillie_Determination, m.Hydrapple_ex, m.Hydrapple_ex, m.Ultra_Ball]
    # The bench already covers the promotion, and both bodies came down this
    # turn, so nothing on it can attack either.
    assert len(mine["bench"]) == 2
    assert all(b["appearThisTurn"] for b in mine["bench"])
    # Nothing of the Hydrapple line is in play: the two Hydrapple ex in hand
    # have nothing to evolve from, this turn or the next.
    assert not any(p["id"] in (m.Applin, m.Dipplin)
                   for p in mine["bench"] + mine["active"])


def test_the_bench_of_two_is_not_deepened_with_two_cards():
    assert _chosen(_obs(_STEP18))["type"] == int(m.OptionType.END)


def test_the_cost_keeps_the_supporter_that_carries_the_next_turn():
    # The counterfactual: if the Ultra Ball IS paid for on this board, what it
    # may not pay with is the Supporter. At HEAD this returned Lillie's +
    # Hydrapple ex; the two dead Hydrapple ex cover the cost on their own.
    assert _discarded_ids(_obs(_STEP19)) == [m.Hydrapple_ex, m.Hydrapple_ex]


# ---------------------------------------------------------------------------
# What the rule does NOT touch
# ---------------------------------------------------------------------------

def test_a_bench_of_one_still_digs_for_a_body():
    """The board the net was built for: one knockout away from no bodies.

    It is also the FIRST Ultra Ball of this very turn (step 12 of the record,
    with a single Ogerpon on the bench), which the agent should keep playing.
    """
    obs = _obs(_STEP18)
    mine = _mine(obs)
    mine["bench"] = mine["bench"][:1]
    assert _chosen(obs)["type"] == int(m.OptionType.PLAY)
