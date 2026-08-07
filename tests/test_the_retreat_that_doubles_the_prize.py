"""The retreat chooses who pays the prize, and it was choosing the ex.

Scenario (user, episode 90481101, turn 6 vs a Teal Mask Ogerpon ex deck, LOST).
The turn ends at step 58 with this board:

    US                                    THEM
    active  Applin 40/40, 1 energy        active  Teal Mask Ogerpon ex 230/230,
    bench   Teal Mask Ogerpon ex                          FIVE energies
            210/210, 2 energies           stadium: Forest of Vitality (ours)
    hand    Meganium

The menu is ATTACK (Tumbling Attack) / RETREAT / END. The agent retreated: it
paid the Applin's Grass, brought up the Ogerpon ex -- which needs THREE energies
for Myriad Leaf Shower and had two, so the next menu was END with no attack in
it -- and handed a 2-prize body to an attacker that resolves
30 + 30x(5 + 2) = 240 against its 210 HP. Leaving the Applin in front hands over
ONE prize for the same knock-out.

The branch that scored it is the generic arm of the NON_ATTACKERS block in
`ptcg/turn/options/retreat.py`: `elif _has_bench_attacker: score = 3000`, which
asked one question -- is there a body from MAIN_ATTACKERS on the bench? -- and
none of the three that decide whether the swap is worth paying for:

  (a) does the relay hand over MORE prizes than the body going down,
  (b) can it attack the turn it goes up,
  (c) does it SURVIVE what the opponent is about to throw at it.

`_pf_every_relay_costs_more` asks all three of every promotable body, and vetoes
the retreat only when EVERY one of them fails all three. Any single escape --
a body that costs no more prizes, one that attacks today, one that lives --
leaves the old score exactly where it was.

The reading of (c) is `_op_active_attack_damage_to(..., scaled=True)`, the same
one the turn plan uses. The blind projector answers the 30 PRINTED on Myriad
Leaf Shower, so with it the rule could never see a knock-out at all; see the
`scaled` docstring in `ptcg/calc/damage.py` for why the accurate number is
admissible in a rule that is new and forbidden in the ones calibrated against
the blind one.

Coverage:
  * the record's board and its decision, on the recorded observation;
  * the three escapes, each one alone, on the same synthetic board;
  * the projection itself: what the blind reading says and what the scaled one
    says about the body we were about to promote.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import OptionType
from state_builder import Scenario, pk

APPLIN = m.Applin
OGERPON = m.Teal_Mask_Ogerpon_ex
DIPPLIN = m.Dipplin

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "ogerpon_step58_the_front_spot_goes_to_the_cheaper_body.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs_step58():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _kind(obs, choice):
    """The type of option the agent picked."""
    assert choice, f"the agent chose nothing: {choice}"
    return OptionType(obs["select"]["option"][choice[0]]["type"])


# ---------------------------------------------------------------------------
# 1. The record
# ---------------------------------------------------------------------------

def test_step58_the_board_is_the_records_one():
    obs = _obs_step58()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    active = mine["active"][0]
    assert active["id"] == APPLIN and active["hp"] == 40
    assert len(active["energies"]) == 1, "one Grass: exactly the retreat cost"

    relay = mine["bench"][0]
    assert relay["id"] == OGERPON and relay["hp"] == 210
    assert len(relay["energies"]) == 2
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON] == 3, (
        "two of the three energies Myriad Leaf Shower costs: promoting it "
        "brings up a body that cannot attack this turn")

    assert theirs["active"][0]["id"] == OGERPON
    assert len(theirs["active"][0]["energies"]) == 5, "the attack scales on these"

    types = {o["type"] for o in obs["select"]["option"]}
    assert int(OptionType.RETREAT) in types and int(OptionType.ATTACK) in types


def test_step58_the_applin_keeps_the_front_spot():
    obs = _obs_step58()
    assert _kind(obs, m.agent(obs)) == OptionType.ATTACK, (
        "the retreat buys no damage, no wall and no tempo -- only a 2-prize "
        "body for the same knock-out the 1-prize Applin was already taking")


def test_step58_what_the_two_projections_say_about_the_relay():
    """Why the rule needs the scaled reading: with the printed one the body we
    were about to promote looks like it survives with 180 HP to spare.

    The decision runs first because the scale is a per-observation snapshot
    (`AGENT_STATE.op_scale`, filled by `agent()`); reading the projector on a
    fresh state measures an empty board, not this one."""
    obs = _obs_step58()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    mine, theirs = st.players[1], st.players[0]
    relay = mine.bench[0]
    op_active = theirs.active[0]

    blind = m._op_active_attack_damage_to(op_active, relay)
    scaled = m._op_active_attack_damage_to(op_active, relay,
                                           theirs.handCount, scaled=True)
    assert blind == 30, "the placeholder printed on Myriad Leaf Shower"
    assert scaled >= (relay.hp or 0), (
        f"30 + 30 x (5 + 1) = {scaled} against 210 HP: the relay dies, and "
        f"the blind {blind} could never have said so")


# ---------------------------------------------------------------------------
# 2. The three escapes, one at a time, on the record's board rebuilt
# ---------------------------------------------------------------------------

def _board(relay=None, op_energies=5):
    """Step 58 as a scenario: the menu is ATTACK / RETREAT / END."""
    return (Scenario(turn=6, step=58, tac=8, first_player=1,
                     energy_played=True, stadium_played=True)
            .my_active(pk(APPLIN, energies=1, fisicas=1))
            .my_bench(relay if relay is not None
                      else pk(OGERPON, energies=2, fisicas=2))
            .op_active(pk(OGERPON, hp=230, max_hp=230, energies=op_energies))
            .op_zones(hand=1, deck=43, prizes=6)
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


def _retreats(obs):
    return _kind(obs, m.agent(obs)) == OptionType.RETREAT


def test_the_synthetic_board_reproduces_the_veto():
    assert not _retreats(_board()), (
        "the control the three that follow are measured against: same board, "
        "no escape, no retreat")


def test_a_relay_that_costs_no_more_prizes_still_takes_the_front():
    """(a) A 1-prize Dipplin instead of the ex. It cannot attack either and it
    dies just the same, but the knock-out costs what it already cost, and the
    swap is free."""
    assert _retreats(_board(relay=pk(DIPPLIN, pre_evo=[APPLIN]))), (
        "the rule is about the prize, not about the retreat")


def test_a_relay_that_attacks_today_still_takes_the_front():
    """(b) The same Ogerpon ex with its third energy. It dies next turn all the
    same -- but it swings first, and a body that pays its own way is not the
    mute one this rule is about."""
    assert _retreats(_board(relay=pk(OGERPON, energies=3, fisicas=3)))


def test_a_relay_that_survives_still_takes_the_front():
    """(c) Their Ogerpon ex with one energy: 30 + 30 x (1 + 1) = 90 against 210
    HP. A relay that lives is the defensive pivot this branch exists for."""
    assert _retreats(_board(op_energies=1))
