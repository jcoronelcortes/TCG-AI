"""The gust KO that took a prize and handed the game back.

Scenario (`records/registro_016_pasos_131_hasta_136.json`, step 133, episode
90093585 vs Crustle -- game LOST):

    US (5 prizes left)                     RIVAL (1 prize left)
    active  Teal Mask Ogerpon ex 90/210    active  Crustle 170/170, 3 energies
            4 Grass                        bench   Mega Kangaskhan ex 300, 1 energy
    bench   Meganium 160                           Dwebble 70
            Meowth ex 170                          Dwebble 70
            Fezandipiti ex 210
            Bayleef 110
    hand    Boss's Orders, Lillie's, Xerosic, two Ogerpon ex

Playing Boss's Orders was right and is not what this file is about: the Crustle
in front cancels ALL damage from our Pokemon ex, so the front takes no prizes
and every prize of the turn is on their bench.

WHICH BODY TO GUST is the decision that lost the game. The agent brought up a
Dwebble, knocked it out for one prize (5 -> 4) and passed. The Crustle walked
straight back into the active spot, Superb Scissors hit our 90 HP Ogerpon ex for
120, and those two prizes were the last one they needed.

THE GAP. `tier_ko` scores a gust KO as if it emptied the active spot. It does
not. The corpse leaves and the opponent PROMOTES whatever they like -- for free,
with no retreat to pay -- so the body that was threatening us is back in front
one action later. A KO that neither wins the game nor removes that body buys a
prize and returns the same board. At their match point that prize is worth
nothing: they close the game before we can spend it.

WHAT THE BOARD OFFERED INSTEAD. The Mega Kangaskhan ex was a trap in three
independent ways at once. It carried ONE energy of the three Rapid-Fire Combo
costs, so it cannot answer even after their attachment. Its retreat costs three
and it cannot pay it, so they cannot walk it back and return the Crustle to the
front. And at 300 HP it does not die to Myriad Leaf Shower this turn, which is
the point rather than a defect: it STAYS in front. Gusting it costs the opponent
their entire turn and parks a 3-prize body where we can chip it down.

THE RULE (`under_denial_the_trap_beats_the_small_ko`) is gated on the turn plan
saying their reply CLOSES the game -- `op_wins_next`, that is MODE_DENY. That is
what makes one more prize worthless, and it is the only situation where a trap
outranks a real KO. A gust that WINS still rules above everything, as it did
before: if the KO ends the game, it ends the game.
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
from ptcg.turn.game_plan import MODE_DENY

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_t16_the_trap_beats_the_small_ko_step133.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
CRUSTLE = m.Crustle_Grass
DWEBBLE = m.Dwebble_Grass
KANGASKHAN = m.Mega_Kangaskhan_ex
SUPERB_SCISSORS = 479


@pytest.fixture(autouse=True)
def reset_main_state():
    """The whole of `AGENT_STATE`: the fixture is replayed COLD and the flags of
    a previous test (the opposing deck detected, the plan of the turn) change
    what the gust selector reads."""
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _sides(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]], cur["players"][1 - cur["yourIndex"]]


def _gusted(obs):
    """The id of the body the agent brings up with Boss's Orders."""
    _, theirs = _sides(obs)
    option = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    return theirs["bench"][option["index"]]["id"]


# --- the three legs of the rule, switched off one at a time ----------------

def _off_match_point(obs):
    """Their prize count away from the end: the reply no longer closes it."""
    _, theirs = _sides(obs)
    theirs["prize"] = [None] * 4
    return obs


def _our_active_survives_the_reply(obs):
    """Superb Scissors does 120: at full HP our Ogerpon ex lives through it."""
    mine, _ = _sides(obs)
    mine["active"][0]["hp"] = mine["active"][0]["maxHp"]
    return obs


def _the_trap_can_answer(obs):
    """A second energy leaves the Mega one attachment from Rapid-Fire Combo, so
    it is no longer a dead body: bringing it up hands them their attacker."""
    _, theirs = _sides(obs)
    trap = theirs["bench"][0]
    trap["energies"] = list(trap["energies"]) + [0]
    trap["energyCards"] = list(trap["energyCards"]) + [
        dict(trap["energyCards"][0], serial=9001)]
    return obs


def _the_small_ko_closes_our_game(obs):
    """One prize left on OUR side: now the Dwebble IS the end of the game."""
    mine, _ = _sides(obs)
    mine["prize"] = [None]
    return obs


# ---------------------------------------------------------------------------
# 1. The board is the one that was recorded
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_gust_that_lost_the_game():
    o = _obs()
    mine, theirs = _sides(o)

    assert o["current"]["turn"] == 16 and o["select"]["context"] == 3
    assert [b["id"] for b in theirs["bench"]] == [KANGASKHAN, DWEBBLE, DWEBBLE]

    # Their match point, and an active we do not damage: the front takes no
    # prizes and their reply takes the last two they need.
    assert len(theirs["prize"]) == 1 and len(mine["prize"]) == 5
    assert theirs["active"][0]["id"] == CRUSTLE
    assert mine["active"][0]["id"] == OGERPON and mine["active"][0]["hp"] == 90
    assert m.attack_table[SUPERB_SCISSORS].damage >= mine["active"][0]["hp"]

    # The Dwebble is a real KO -- the rule is not dodging an imaginary prize --
    # and the Mega is not: 300 HP against Myriad Leaf Shower.
    trap, dwebble = theirs["bench"][0], theirs["bench"][1]
    assert dwebble["hp"] == 70 and trap["hp"] == 300

    # ...and the Mega is trapped twice over: it cannot attack and cannot leave.
    st = m.to_observation_class(o).current
    body = st.players[1 - st.yourIndex].bench[0]
    assert m._op_body_is_harmless(body)
    assert len(body.energies) < m.RETREAT_COST[KANGASKHAN]
    assert m.prize_count_op(body) == 3


def test_the_plan_reads_the_turn_as_denial():
    m.agent(_obs())
    plan = m.AGENT_STATE.turn_plan
    assert plan.op_wins_next and plan.mode == MODE_DENY, (
        "the gate of the rule is the plan: their reply closes the game")
    assert plan.win_route == "", "no route of ours ends it this turn"


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_gust_parks_the_mega_instead_of_taking_the_dwebble():
    assert _gusted(_obs()) == KANGASKHAN, (
        "at their match point the one-prize KO does not stop the reply; the "
        "body that cannot attack and cannot retreat does")


# ---------------------------------------------------------------------------
# 3. Controls: every leg of the gate, and the winning gust above it
# ---------------------------------------------------------------------------

def test_control_away_from_their_match_point_the_ko_is_still_the_target():
    assert _gusted(_off_match_point(_obs())) == DWEBBLE, (
        "with prizes still to take from them the KO keeps its priority")


def test_control_an_active_that_survives_keeps_the_ko():
    assert _gusted(_our_active_survives_the_reply(_obs())) == DWEBBLE, (
        "the denial is only worth a turn when their reply would end the game")


def test_control_a_trap_that_can_answer_is_not_a_trap():
    assert _gusted(_the_trap_can_answer(_obs())) == DWEBBLE, (
        "one attachment away from attacking, the Mega is their attacker and "
        "gusting it does their work")


def test_control_the_gust_that_wins_still_rules():
    assert _gusted(_the_small_ko_closes_our_game(_obs())) == DWEBBLE, (
        "with one prize left the Dwebble ENDS the game: nothing outranks that")
