"""A bench slot is not worth two cards of hand, and never worth tomorrow's hand.

Scenario (`records/registro_002_pasos_011_hasta_026.json`, step 22, turn 2,
episode 90088766 vs Marnie -- WON in spite of this):

    US (6 prizes)                          RIVAL (Marnie)
    active  Fezandipiti ex 210, 1 {G}      active  Marnie's Impidimp 70
    bench   Meowth ex 170     (fresh)      bench   Munkidori 110, Impidimp x2,
            Teal Mask Ogerpon ex 210 (fresh)       Marnie's Morgrem
    hand    Unfair Stamp, Night Stretcher, **Ultra Ball**,
            Hydrapple ex, **Lillie's Determination**
    turn's Supporter: ALREADY SPENT (a Lillie's, earlier in the turn)
    menu:   PLAY Ultra Ball / RETREAT / END      <- there is NO attack

The turn's Supporter was spent and then Meowth ex's Last-Ditch Catch fetched a
SECOND Lillie's Determination: the card that restarts the hand next turn, and
the only one, since the opposing Impidimp -- even after it evolves -- does not
take the 210 HP active down. The agent played the Ultra Ball, paid its two
discards with Night Stretcher AND that Lillie's, and fetched an Applin: 40 HP,
no Dipplin in play or in hand, put down this turn so it cannot evolve either.
Two cards of hand and the whole engine of the next turn, for one bench slot.

Three layers each did their job locally and the mistake came out of the seam:

  * `_score_ultra_ball_play` vetoed it correctly (-1);
  * the STERILE-TURN NET lifted it to 200, because `_st_basic_useful` only
    asked for a bench with room and a basic in the deck;
  * the `SelectContext.DISCARD` block priced the hand Night Stretcher 30,
    **Lillie's 14**, Hydrapple ex 12, Unfair Stamp never -- so the cost took
    the two most expensive, and Lillie's was one of them.

TWO RULES, both about the shape of the board and the hand, neither naming a
matchup:

1. **A body that only sits on the bench rescues nothing once the bench already
   covers the promotion** (`_st_basic_useful`, ptcg/turn/finalize.py). The
   evolution branch of the same net was already sharpened to "it has to evolve
   TODAY"; the basic branch kept the loose reading. The user states the
   criterion: the only reasons to pay for an Ultra Ball are to be able to
   ATTACK, or to stop being one knockout away from having no bodies. This net
   only fires on turns with no attack, so what is left is bench depth --
   `bench_count <= 1`, which is also the board the net was built on (the
   crustle t2 case with a bench of one). The item lock keeps the old reading:
   there the Ultra Ball is use-it-or-lose-it.

2. **A lone refill Supporter is protected BECAUSE the turn's Supporter is
   spent, not despite it** (`_protect_refresh_supporter`,
   ptcg/turn/options/card.py). The old gate was `not state.supporterPlayed`,
   which inverted the valuation exactly where it hurts: this block prices a
   card by what it does NOW, so a Supporter that can no longer be played fell
   from 2 to 14 and became the cheapest thing in the hand. With the slot
   already spent nothing can compete for it next turn -- that is when it is
   worth most.

`_ub_real_fodder` is deliberately NOT changed to match. It models what the
discard scorer lets go, and mirroring rule 2 there kills the two measured
counter-examples of the sterile net (`abomasnow_t6_ub_con_budew_rival` and
`abomasnow_t6_ub_preevo_evolucionable`, pinned in
tests/test_ultra_ball_does_not_burn_the_last_supporters.py) plus the control in
tests/test_ub_does_not_burn_the_freshly_dug_xerosic.py. It over-counts by one
Supporter now, always in the direction of allowing more Ultra Balls, which is
the conservative side of the seam.

Measured. Golden corpus: 2 flips, both in this turn (action 12 `PLAY Ultra
Ball` -> `END`, action 13 the counterfactual cost). Shadow of two trees, 200
mirror games / 24304 decisions: **51 flips = 0.21%**, and every one of them in
the intended direction -- 33 are `PLAY Ultra Ball` -> `END` with no reverse
case, 18 are costs that keep the Lillie's/Dawn and pay with something else.
Head-to-head n=1000: 52.1% [49.0-55.2], 0 forfeits, prizes +0.18, against a
same-session mirror control of 48.2% [45.1-51.3] -- neutral, the winrate cannot
resolve a rule that fires twice a game.
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

_STEP22 = ROOT / "tests" / "fixtures" / (
    "marnie_t2_ultra_ball_burns_tomorrow_supporter_step22.json")
_STEP23 = ROOT / "tests" / "fixtures" / "marnie_t2_ultra_ball_cost_step23.json"


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
    obs = _obs(_STEP22)
    cur = obs["current"]
    mine = _mine(obs)

    assert cur["turn"] == 2 and cur["supporterPlayed"]
    # No attack in the menu: the turn IS sterile, which is what wakes the net.
    types = [o["type"] for o in obs["select"]["option"]]
    assert int(m.OptionType.ATTACK) not in types
    assert int(m.OptionType.END) in types

    assert [c["id"] for c in mine["hand"]] == [
        m.Unfair_Stamp, m.Night_Stretcher, m.Ultra_Ball,
        m.Hydrapple_ex, m.Lillie_Determination]
    # The bench already covers the promotion, and both bodies came down this
    # turn, so nothing on it can attack either.
    assert len(mine["bench"]) == 2
    assert all(b["appearThisTurn"] for b in mine["bench"])
    # Nothing of the Hydrapple line is in play: the Applin the Ultra Ball went
    # for could not evolve this turn nor the next.
    assert not any(b["id"] in (m.Applin, m.Dipplin)
                   for b in mine["bench"] + mine["active"])


def test_the_bench_slot_is_not_bought_with_two_cards():
    assert _chosen(_obs(_STEP22))["type"] == int(m.OptionType.END)


def test_the_cost_keeps_the_supporter_that_carries_the_next_turn():
    # The counterfactual: if the Ultra Ball IS paid for on this board, what it
    # may not pay with is the Supporter. Before the fix this returned Night
    # Stretcher + Lillie's.
    assert m.Lillie_Determination not in _discarded_ids(_obs(_STEP23))


# ---------------------------------------------------------------------------
# What the two rules do NOT touch
# ---------------------------------------------------------------------------

def test_a_bench_of_one_still_digs_for_a_body():
    """The board the net was built for: one knockout away from no bodies."""
    obs = _obs(_STEP22)
    mine = _mine(obs)
    mine["bench"] = mine["bench"][:1]
    assert _chosen(obs)["type"] == int(m.OptionType.PLAY)


def test_the_lone_refresh_supporter_is_not_protected_when_there_are_two():
    """The protection is for the LAST copy; a spare is fodder as before."""
    obs = _obs(_STEP23)
    hand = _mine(obs)["hand"]
    hand.append({"id": m.Lillie_Determination, "playerIndex": 1, "serial": 86})
    obs["select"]["option"].append(
        {"type": 3, "area": 2, "index": len(hand) - 1, "playerIndex": 1})
    assert m.Lillie_Determination in _discarded_ids(obs)
