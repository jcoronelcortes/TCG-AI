"""The turn plan pointed at the bench, and by the end of the turn it lied.

Scenario (`records/registro_004_pasos_018_hasta_031.json`, episode 90588326,
step 28, turn 4 vs Alakazam, game WON):

    US (6 prizes)                             RIVAL (Alakazam)
    active  Teal Mask Ogerpon ex 210/210,     active  Abra 50/50, 0 energy
            **2 Grass**                       bench   Abra 50/50
    bench   Bayleef 110, 0
            **Teal Mask Ogerpon ex 210/210,
            2 Grass**  <- the twin
            Meowth ex 170, 0
    hand    Meganium, Ultra Ball              menu    RETREAT / END TURN

Myriad Leaf Shower costs three. Neither Ogerpon has three, there is no Grass
left in hand, and the engine offers no ATTACK at all -- the whole menu is
"retreat" or "end the turn". The agent retreated: one Grass to the discard to
put in front an Ogerpon ex with the same species, the same printed HP, the same
current HP and the same two energies. The swap bought nothing and cost the fee.

WHY IT FIRED. `AGENT_STATE.plan.attacker` is chosen ONCE per turn, and the loop
that chooses it only overwrites the pointer when it finds a BETTER route -- never
when the route it already wrote stops existing. On step 18, opening the same
turn, the benched Ogerpon was a legitimate plan: two energies plus the Grass
then in hand reaches Myriad. That Grass did get attached -- by Teal Dance, and
to the ACTIVE Ogerpon, which is another body. The pointer survived the turn that
spent what backed it, and the `plan.attacker >= 1` branch of the retreat scorer
cashed it for 3500: "the plan says the bench attacks and the active cannot, so
retreat".

THE FIX (`ptcg/turn/options/retreat.py`). Before that branch trusts the pointer,
the body it points at is asked again whether it can attack TODAY, with
`_reachable_grass_for` -- which is WIDER than the test the plan itself used (it
also counts Teal Dance / Ripening Charge and the Grass the retreat fee is about
to send to the discard). A pointer that is still valid always survives the
re-reading; only an expired promise falls through, and then the chain reasons as
if there were no plan. On this board the generic branch below already knows the
answer: no ready relay on the bench, so no retreat.

This is the same sentence as `test_the_retreat_fee_needs_somebody_to_hand_over
_to.py` -- a fee is only worth paying when the body it hands over to can DO
something -- read at the other end of the turn: there the charge that pays it,
here the retreat itself.

Measured (see the commit): 0 flips in 1000 mirror games, 3-6 per 300 games
against most bot lists and 31 against `crustle_wall_6`; winrate NEUTRAL in the
mirror (50.0% [46.9-53.1] against a 52.1% control) and unchanged vs the
Alakazam and Crustle bots. It is kept under the exception of the neutral policy:
the score was paying for a route the engine does not offer.
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
from cg.api import OptionType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t4_the_plan_pointer_expires_step28.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
BAYLEEF = m.Bayleef
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
ULTRA_BALL = m.Ultra_Ball
ABRA = 741
MYRIAD_LEAF_SHOWER = 120

# The recorded menu of step 28, in order.
RETREAT = 0
END_TURN = 1


@pytest.fixture(autouse=True)
def reset_main_state():
    """The bug lives in state carried BETWEEN calls (the turn plan), so every
    test starts from a cold agent and replays the opening of the turn itself."""
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _frames():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return {item["step"]: copy.deepcopy(item["observation"])
            for item in data["sequence"]}


def _decide(obs):
    """The real decision, with the opening of the turn replayed before it.

    `plan.attacker` is written on the turn's first menu (step 18) and is never
    recomputed afterwards; replaying step 28 cold leaves the pointer at -1 and
    the branch under test is never reached.
    """
    m.agent(_frames()[18])
    return m.agent(obs)


def _with_a_grass_in_hand(obs):
    """The same board with one Basic Grass still in hand: the plan's premise is
    alive again -- the benched twin reaches Myriad Leaf Shower this turn."""
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    mine["hand"] = mine["hand"] + [{"id": m.Basic_Grass_Energy,
                                    "playerIndex": cur["yourIndex"],
                                    "serial": 999}]
    mine["handCount"] = len(mine["hand"])
    return obs


# ---------------------------------------------------------------------------
# 1. The board is the one that was recorded
# ---------------------------------------------------------------------------

def test_the_board_of_step_28_is_two_identical_ogerpon():
    obs = _frames()[28]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    active = mine["active"][0]
    twin = mine["bench"][1]
    assert active["id"] == OGERPON and twin["id"] == OGERPON
    assert len(active["energies"]) == len(twin["energies"]) == 2
    assert active["hp"] == twin["hp"] == 210, "same species, same current HP"
    assert [b["id"] for b in mine["bench"]] == [BAYLEEF, OGERPON, MEOWTH]

    assert [c["id"] for c in mine["hand"]] == [MEGANIUM, ULTRA_BALL], (
        "no Grass left in hand: nothing can reach the third energy")
    assert theirs["active"][0]["id"] == ABRA


def test_the_menu_offers_no_attack_at_all():
    """The route the 3500 was paying for is not on the menu: Myriad Leaf Shower
    costs three and both twins carry two."""
    opts = _frames()[28]["select"]["option"]
    assert [o.get("type") for o in opts] == [int(OptionType.RETREAT),
                                             int(OptionType.END)]
    assert m.attack_table[MYRIAD_LEAF_SHOWER].energies == [1, 1, 1]
    assert not m._can_attack_eff(OGERPON, 2)


# ---------------------------------------------------------------------------
# 2. The pointer that expired
# ---------------------------------------------------------------------------

def test_the_plan_still_points_at_the_benched_twin():
    """Written on step 18 and never revised: attacker 2 is bench index 1."""
    m.agent(_frames()[18])
    assert m.AGENT_STATE.plan.attacker == 2

    obs = _frames()[28]
    m.agent(obs)
    assert m.AGENT_STATE.plan.attacker == 2
    cur = obs["current"]
    relay = cur["players"][cur["yourIndex"]]["bench"][m.AGENT_STATE.plan.attacker - 1]
    assert relay["id"] == OGERPON and len(relay["energies"]) == 2, (
        "the pointer names a body that can no longer attack")


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_turn_ends_instead_of_swapping_twin_for_twin():
    assert _decide(_frames()[28]) == [END_TURN], (
        "retreating pays one Grass to put in front the same species with the "
        "same energy and the same HP: the swap buys nothing")


def test_the_retreat_comes_back_when_the_relay_can_still_attack():
    """Counterfactual: one Grass in hand and the pointer is honest again --
    the twin reaches Myriad Leaf Shower, so handing it the front spot is worth
    the fee."""
    assert _decide(_with_a_grass_in_hand(_frames()[28])) == [RETREAT]
