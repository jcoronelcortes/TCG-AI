"""The Grass that creates the knockout goes to the ACTIVE on any turn.

Scenario (`records/registro_014_pasos_156_hasta_169.json`, episode 92354161,
step 165, turn 14 vs Dragapult ex, LOST):

    US (1 prize)                        RIVAL (2 prizes)
    active Teal Mask Ogerpon ex          active Dragapult ex 320/320,
           10/210, 6 effective energy           2 energies
    bench  Meowth ex, Ogerpon ex,        bench  Meowth ex, Ogerpon ex(2),
           Meganium, Fezandipiti ex,            Meganium(2), Fezandipiti ex
           Applin
    hand   Ultra Ball, Basic {G} Energy   the manual attachment UNSPENT

Myriad Leaf Shower counts the energy on BOTH active Pokemon, so it stands at
30 + 30x(6+2) = 270 into 320 HP. Meganium's Wild Growth doubles a physical
Grass, so the one card in hand is worth two effective energy ON THE ATTACKER:
30 + 30x(8+2) = 330. Their ex, and we were on our last prize -- the game, from
a menu whose only question was which body gets the card.

It went to a benched Applin (23500 in the energy scorer, against 8250 for the
active). `_charge_active_finishes` is the rule written for exactly this --
"the charge that finishes goes to the active, ahead of every energy cap" -- and
two separate readings kept it quiet:

  * it only looked at boards where the active could not yet PAY for its attack
    (`_cav_e < _cav_req`), and an Ogerpon at 6 pays a cost of 3 twice over.
    Fixed in August 2026 for `records/registro_010` -- the same shape, an
    Archaludon ex a single Grass out of reach;
  * ...but gated on `TurnPlan.do_or_die`, 0.50% of the frozen corpus. This turn
    opens in mode RACE, the gate stayed shut, and the fix could not see the
    board it was written for.

The gate is gone: the branch asks the central evaluators whether the charge
reaches the HP in front, and nothing else. What it gained in reach it gives
back in a second question -- whether the DESTINATION is what makes the
knockout. Syrup Storm counts the Grass on our whole field and knocks out from
wherever the card lands, so there this rule has no say and the bench hygiene
that decides it keeps its own (`test_marnie_phases_c_and_e_bench_hygiene`).

Frame 165 is the record's own menu. 166 is the board the corrected attachment
leaves, rebuilt by hand, because the real game spent that Grass on the Applin.
900 is the control: one physical Grass fewer on the active, no reachable charge
reaches 320, and the destination goes back to the ladder that always decided
it.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "dragapult_t14_the_winning_grass_and_the_bench.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
APPLIN = m.Applin
DRAGAPULT = 121
MYRIAD_LEAF_SHOWER = 120


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
    yield
    m._init_cards_tracking()


def _frame(step):
    """One menu of the fixture, replayed COLD.

    The three frames are ALTERNATIVES, not a sequence: 166 is the board 165
    produces and 900 is 165 with a body changed, so each one opens its own turn
    plan. That is also the point of the test -- the turn these menus open is
    mode RACE, and the rule has to speak anyway.
    """
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    for item in data["sequence"]:
        if item["step"] == step:
            return copy.deepcopy(item["observation"])
    raise KeyError(step)


def _destination(obs, choice):
    """The id of the body the chosen ATTACH charges, or None if it is not one."""
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != int(m.OptionType.ATTACH):
        return None
    us = obs["current"]["players"][obs["current"]["yourIndex"]]
    if opt.get("inPlayArea") == int(m.AreaType.ACTIVE):
        return us["active"][0]["id"]
    return us["bench"][opt["inPlayIndex"]]["id"]


def test_the_turn_is_not_do_or_die():
    """The premise of the whole file: this board had no licence from the plan."""
    obs = _frame(165)
    m.agent(obs)
    assert m.AGENT_STATE.turn_plan_open.do_or_die is False, (
        "the turn opens in mode RACE -- if it ever opens DENY the fix under "
        "test is not the one being measured here")


def test_the_winning_grass_goes_to_the_active():
    obs = _frame(165)
    assert _destination(obs, m.agent(obs)) == OGERPON, (
        "one physical Grass on the ACTIVE Ogerpon is 30 + 30x(8+2) = 330 into "
        "a 320 HP Dragapult ex, on our last prize. On the benched Applin it is "
        "a body that does not attack this turn or any other")


def test_and_then_it_attacks():
    obs = _frame(166)
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("type") == int(m.OptionType.ATTACK), (
        "with the eighth effective energy on it the Ogerpon does not retreat "
        "and does not develop: it swings")
    assert opt.get("attackId") == MYRIAD_LEAF_SHOWER


def test_the_projection_is_the_one_that_wins():
    """The arithmetic the decision rests on, asked of the damage evaluator
    itself rather than restated here: `_attacker_base_damage` is what taught
    this agent that Myriad Leaf Shower reads BOTH actives."""
    obs = _frame(166)
    cur = obs["current"]
    us = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]
    ours = len(us["active"][0]["energies"])
    theirs = op["active"][0]["energies"]
    assert us["active"][0]["id"] == OGERPON and ours == 8
    assert op["active"][0]["id"] == DRAGAPULT and len(theirs) == 2

    target = type("T", (), {"id": DRAGAPULT, "hp": 320, "energies": theirs})()
    damage = m._attacker_base_damage(OGERPON, target, ours,
                                     grass_scale=0, teal_self_energy=ours,
                                     bench_count=len(us["bench"]))
    assert damage == 330 >= op["active"][0]["hp"] == 320


def test_control_with_the_knockout_out_of_reach_the_ladder_decides():
    """One physical Grass fewer on the active: 30 + 30x(6+2) = 270 into 320 and
    no second card to reach it. The rule that walks over every energy cap has
    to stay silent, and the destination is the one it always was."""
    obs = _frame(900)
    assert _destination(obs, m.agent(obs)) == APPLIN, (
        "with no knockout to buy, where the Grass goes is decided by the "
        "development ladder exactly as before")
