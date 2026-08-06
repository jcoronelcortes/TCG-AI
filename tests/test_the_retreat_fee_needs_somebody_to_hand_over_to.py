"""The retreat fee paid on a body that had nowhere to go.

Scenario (`records/registro_002_pasos_014_hasta_027.json`, step 18, episode
90114194 vs Mega Lopunny -- game WON, this turn wasted):

    US (6 prizes, turn 2, our first)       RIVAL (Mega Lopunny)
    active  Chikorita 70, 0 energy         active  Buneary 70, 1 Spiky Energy
    bench   Teal Mask Ogerpon ex 210, 0            + Air Balloon
            Applin 40, 0                   bench   Buneary, Dunsparce, Fan Rotom,
    hand    Boss's Orders, Forest of               Dunsparce, Buneary
            Vitality, **1 Grass**, Dawn,
            Hydrapple ex

One Grass in hand, and three ways to spend it: the manual attachment on the
active Chikorita, the same attachment on a benched body, or the Teal Dance of
the benched Ogerpon ex -- which attaches that same Grass, DRAWS a card and does
NOT consume the turn's attachment.

The agent charged the Chikorita (31210, over Teal Dance at 7500), and the rest
of the turn shows what it bought: Dawn, a second Ogerpon to the bench, RETREAT
-- paying with the Grass it had just attached -- and the Ogerpon ex promoted at
0 energy. Myriad Leaf Shower costs three, so the menu of the next step offers
PLAY and END and no ATTACK at all. The Grass went from the hand to the discard,
the turn neither attacked nor drew a card.

WHY THE CHARGE WON. Chikorita and Bayleef are not attackers -- Growl does no
damage -- so the energy on them buys exactly ONE thing: the retreat cost. The
23200 of that branch is the FEE OF A PIVOT, and it was unconditional. The
branches right below it, for an active Meowth ex and an active Fezandipiti ex,
ask the question this one did not ("we only charge it when the retreat is
NECESSARY, that is, when there is a real attacker on the bench to promote"), and
even they settle for the attacker's ID being on the bench -- which on this board
an Ogerpon ex at 0 energy would have passed.

WHAT THIS IS NOT. It is not the doomed-active machinery. Their Buneary holds one
energy and Kick costs two, so on their next turn it can only Run Around for 0:
`active_ko_likely` reads False, and correctly. The fee is not wrong here because
the body paying it is about to die -- it is wrong because the body it hands over
to cannot attack either. That is the same line `test_the_one_prize_wall_takes_
the_front.py` already draws for the pivot itself: the prize arm fires when the
fee is ALREADY on the active, and never diverts the turn's one attachment to a
body we are about to walk away from.

THE ARM THAT SURVIVES: put three Grass on that same benched Ogerpon and the fee
is paid again -- there the retreat buys a Myriad Leaf Shower, and the energy on
the Chikorita is the cheapest way to reach it.
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
            / "lopunny_t2_the_retreat_fee_needs_a_relay_step18.json")

CHIKORITA = m.Chikorita
OGERPON = m.Teal_Mask_Ogerpon_ex
APPLIN = m.Applin
BUNEARY = 848
MYRIAD_LEAF_SHOWER = 120
RUN_AROUND = 1223
KICK = 1224

# The option indices of the recorded menu (asserted in the first test).
ATTACH_TO_ACTIVE = 2
ATTACH_TO_BENCHED_OGERPON = 3
TEAL_DANCE = 6


@pytest.fixture(autouse=True)
def reset_main_state():
    """The whole of `AGENT_STATE`, not just the card tracking: this fixture is
    replayed COLD, and the flags of a previous test (the opposing deck
    detected, the plan of the turn) change what the charges read."""
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _with_a_ready_relay(obs):
    """The same turn with the benched Ogerpon ex already at three Grass: the
    retreat now buys an attack, so the fee is worth the turn's attachment."""
    cur = obs["current"]
    ogerpon = cur["players"][cur["yourIndex"]]["bench"][0]
    ogerpon["energies"] = [1, 1, 1]
    ogerpon["energyCards"] = [{"id": 1, "playerIndex": cur["yourIndex"],
                               "serial": 900 + k} for k in range(3)]
    return obs


# ---------------------------------------------------------------------------
# 1. The board is the one that was recorded
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_that_was_wasted():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 2 and not cur["energyAttached"]
    assert mine["active"][0]["id"] == CHIKORITA
    assert mine["active"][0]["energies"] == [], "nothing to pay a retreat with"
    assert [(b["id"], len(b["energies"])) for b in mine["bench"]] == [
        (OGERPON, 0), (APPLIN, 0)], "the whole bench is at zero energy"
    assert sum(1 for c in mine["hand"] if c["id"] == m.Basic_Grass_Energy) == 1

    assert theirs["active"][0]["id"] == BUNEARY

    opts = o["select"]["option"]
    assert opts[ATTACH_TO_ACTIVE]["inPlayArea"] == int(m.AreaType.ACTIVE)
    assert opts[ATTACH_TO_BENCHED_OGERPON]["inPlayIndex"] == 0
    assert opts[TEAL_DANCE]["type"] == int(OptionType.ABILITY), (
        "the Teal Dance of the benched Ogerpon ex is on the menu")


# ---------------------------------------------------------------------------
# 2. What the fee actually bought, checked against the card table
# ---------------------------------------------------------------------------

def test_the_body_we_would_promote_cannot_attack():
    """Myriad Leaf Shower costs three: the recorded retreat promoted a mute
    Ogerpon ex, and the engine offered no ATTACK on the next step."""
    assert m.attack_table[MYRIAD_LEAF_SHOWER].energies == [1, 1, 1]
    assert not m._can_attack_eff(OGERPON, 0)
    assert not m._can_attack_eff(APPLIN, 0)


def test_the_active_is_not_doomed_so_this_is_not_the_doomed_machinery():
    """Their Buneary holds ONE energy: Kick costs two, Run Around does 0."""
    o = _obs()
    cur = o["current"]
    theirs = cur["players"][1 - cur["yourIndex"]]
    assert len(theirs["active"][0]["energies"]) == 1
    assert m.attack_table[RUN_AROUND].damage == 0
    assert m.attack_table[KICK].energies == [0, 0]

    state = m.to_observation_class(o).current
    mine_active = state.players[state.yourIndex].active[0]
    op_active = state.players[1 - state.yourIndex].active[0]
    assert m._op_active_attack_damage_to(op_active, mine_active) < mine_active.hp


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_the_grass_goes_to_teal_dance_not_to_the_retreat_fee():
    action = m.agent(_obs())
    assert action == [TEAL_DANCE], (
        "Teal Dance attaches the same Grass to the body being assembled, draws "
        "a card and leaves the turn's manual attachment free")


def test_the_fee_is_paid_again_once_the_relay_can_attack():
    action = m.agent(_with_a_ready_relay(_obs()))
    opt = _obs()["select"]["option"][action[0]]
    assert action == [ATTACH_TO_ACTIVE]
    assert opt["inPlayArea"] == int(m.AreaType.ACTIVE), (
        "with a Myriad Leaf Shower waiting behind it, the Grass on the "
        "Chikorita is the cheapest way to reach it")
