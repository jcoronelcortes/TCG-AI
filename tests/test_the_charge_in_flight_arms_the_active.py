"""A charge already in the engine's hand is not a projection.

Record (user, `records/registro_004_pasos_036_hasta_057.json` step 56, episode
92558163 vs a Marnie deck, LOST). Our turn 4, and the board was a knockout
waiting to be collected:

    US                                        THEM
    active  Tapu Bulu 140/140, TWO of the     active  Applin 70/70
            four effective Wood Hammer
            needs (Meganium doubles each
            Grass, so ONE card closes it)
    bench   Meganium, Meowth ex, Hydrapple    bench   Dipplin, Meowth ex,
            ex JUST evolved, and two Teal             Applin, two Teal Mask
            Mask Ogerpon ex                          Ogerpon ex
    hand    ONE Basic {G} Energy -- and the Hydrapple's Ripening Charge was
            holding it, asking us which body to put it on

Wood Hammer takes their 70 HP active. The agent put the Grass on a benched
Ogerpon ex, which cannot attack this turn -- promoting it needs a retreat of
three the Tapu could not pay -- and ended the turn without attacking.

WHY IT NEVER SAW THE LINE. `_charge_active_finishes` (main.py) is the rule that
answers "can the active ATTACK today if I take it the energy I can still move?",
and it never even looked, because the budget it asks for first came back at
zero. That budget is the turn's manual attachment (already spent) plus
`_grass_ability_slots_active` (ptcg/calc/energy.py) -- the charging abilities
that can reach the ACTIVE.

That function counted a SUBSET as capacity (Ripening Charge reaches anybody,
Teal Dance only the Ogerpon that used it) and subtracted the WHOLE set as
spent. Two benched Teal Dances had fired that turn, so a capacity of one came
out at zero: it reported no route to the active while the engine was, at that
very moment, holding a Ripening Charge open and offering the active as one of
its targets. The active fell to the generic development band (31210) and a
benched Ogerpon's lethal-focus band (41700) took the Grass.

THE TWO HALVES OF THE FIX, and each one closes the record on its own:

  * every charge is billed to the capacity that spent it. A Grass on a benched
    Teal Mask Ogerpon ex is that Ogerpon's own dance -- a route that was never
    in this capacity -- so it is not billed to the Ripening Charge that is
    still live (`_grass_attach_targets_this_turn`, main.py);
  * and when the menu we are answering IS a charging ability's target select
    with the ACTIVE among its options, the route is not projected at all: that
    Grass lands wherever we point it, so the budget has a floor of one.

Both read our own board and our own arithmetic -- which of our bodies took a
Grass today, what each of our two charging abilities can reach, what the active
costs to attack with -- so they say the same thing against every deck.

WHAT IT FLIPPED in the frozen corpus (3 580 recorded decisions, 50 games): three,
all of them the same rule finally seeing a charge it had been blind to, and all
three moving the energy onto a body that attacks TODAY --

  * registro_037 turn 10: the ACTIVE Ogerpon ex dances for itself instead of a
    benched one. Two charges take it from four effective to eight, and Myriad
    Leaf Shower counts both actives: 30 + 30x11 = 360 against a 320 HP
    Dragapult ex;
  * registro_041 turn 15: the Grass arms the ACTIVE Meganium's Solar Beam
    against their Hydrapple ex at 60 of 330 -- a knockout, where the golden
    decision developed a benched Ogerpon;
  * registro_043 turn 8: same shape without the knockout. The bench was ready
    but the turn had already retreated, so the active Meganium was the only
    body that could attack at all; the Grass now arms it instead of sitting on
    a benched Hydrapple.

Coverage: the record's board; the boundary where the charge no longer reaches
the cost; each half of the fix with the other one switched off; and the
accounting predicate on its own.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType
from golden_corpus import reset_agent

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step56_the_charge_that_arms_the_active.json")

GRASS = m.Basic_Grass_Energy
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _board():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _decide(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


# ---------------------------------------------------------------------------
# 0. The board is the record's, and the ACTIVE really is on the menu
# ---------------------------------------------------------------------------

def test_the_menu_is_the_ripening_charge_asking_where_the_grass_goes():
    obs = _board()
    select = obs["select"]
    assert select["effect"]["id"] == HYDRAPPLE, (
        "the select has to be the Hydrapple ex's charging ability")
    assert any(o["area"] == int(AreaType.ACTIVE) for o in select["option"]), (
        "the ACTIVE has to be one of the bodies the ability offers")

    mine = _mine(obs)
    tapu = mine["active"][0]
    assert tapu["id"] == TAPU and len(tapu["energies"]) == 2, (
        "the active Tapu Bulu carries two of the four effective Wood Hammer needs")
    assert sum(1 for b in mine["bench"] if b and b["id"] == OGERPON) == 2
    assert sum(1 for b in mine["bench"] if b and b["id"] == HYDRAPPLE) == 1

    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    assert op["active"][0]["hp"] == 70, (
        "their active at 70 HP is what makes the charge a prize and not development")


def test_the_turn_had_already_spent_its_manual_attachment_and_two_dances():
    """Without that history the estimate was never wrong in the first place."""
    obs = _board()
    assert obs["current"]["energyAttached"] is True
    attaches = [l for l in obs["logs"]
                if l.get("type") == 11 and l.get("cardId") == GRASS]
    assert len(attaches) == 3, "one manual attachment and two Teal Dances"
    m.agent(copy.deepcopy(obs))
    assert m.AGENT_STATE._grass_attaches_this_turn == 3
    assert m.AGENT_STATE._grass_attach_targets_this_turn == {63, 64, 83}


# ---------------------------------------------------------------------------
# 1. The record's board: the Grass arms the body in front
# ---------------------------------------------------------------------------

def test_the_charge_goes_to_the_active_that_it_arms():
    obs = _board()
    option = _decide(obs)
    assert option["area"] == int(AreaType.ACTIVE), (
        "one Grass takes the Tapu Bulu to Wood Hammer and Wood Hammer takes "
        f"their 70 HP active; chose {option}")


# ---------------------------------------------------------------------------
# 2. Each half of the fix closes the record on its own
# ---------------------------------------------------------------------------

def test_the_accounting_alone_closes_it(monkeypatch):
    """With the in-flight floor switched off, the billing fix still finds it."""
    monkeypatch.setattr(m, "SelectContext", _NoAttachFrom(m.SelectContext))
    option = _decide(_board())
    assert option["area"] == int(AreaType.ACTIVE), f"chose {option}"


def test_the_in_flight_floor_alone_closes_it(monkeypatch):
    """With the billing fix switched off -- the old, blind estimate -- the
    floor still finds it: the engine is holding the route open."""
    monkeypatch.setattr(m, "_grass_ability_slots_active",
                        lambda state, my_state, field_counts: 0)
    option = _decide(_board())
    assert option["area"] == int(AreaType.ACTIVE), f"chose {option}"


class _NoAttachFrom:
    """`SelectContext` with ATTACH_FROM moved out of reach, so the in-flight
    clause cannot match. Everything else is the real enum."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        if name == "ATTACH_FROM":
            return -1
        return getattr(self._real, name)


# ---------------------------------------------------------------------------
# 3. The boundary: a charge that arms nothing does not claim the active
# ---------------------------------------------------------------------------

def test_a_tapu_out_of_reach_of_its_cost_does_not_take_the_charge():
    """At ZERO effective energy one Grass leaves the Tapu at two of four: it
    still cannot attack, so the rule has nothing to say and the destination
    goes back to the bench."""
    obs = _board()
    tapu = _mine(obs)["active"][0]
    tapu["energies"] = []
    tapu["energyCards"] = []
    option = _decide(obs)
    assert option["area"] != int(AreaType.ACTIVE), (
        f"the charge buys no attack there; chose {option}")


def test_an_active_that_already_attacks_does_not_claim_the_charge():
    """At four effective the Tapu already pays Wood Hammer: the extra Grass
    adds nothing to a flat attack and belongs somewhere else."""
    obs = _board()
    tapu = _mine(obs)["active"][0]
    tapu["energies"] = [GRASS] * 4
    tapu["energyCards"] = [{"id": GRASS, "playerIndex": 1, "serial": 900 + k}
                           for k in range(2)]
    option = _decide(obs)
    assert option["area"] != int(AreaType.ACTIVE), (
        f"a body already at its cost is not this rule's business; chose {option}")


# ---------------------------------------------------------------------------
# 4. The accounting predicate on its own
# ---------------------------------------------------------------------------

def _slots_active(obs):
    from collections import defaultdict
    from ptcg.calc.energy import _grass_ability_slots_active
    state = m.to_observation_class(copy.deepcopy(obs)).current
    mine = state.players[state.yourIndex]
    counts = defaultdict(int)
    for p in list(mine.active or []) + list(mine.bench or []):
        if p is not None:
            counts[p.id] += 1
    return _grass_ability_slots_active(state, mine, counts)


def test_a_benched_dance_is_not_billed_to_the_ripening_charge():
    obs = _board()
    m.agent(copy.deepcopy(obs))
    assert _slots_active(obs) == 1, (
        "the Hydrapple ex's Ripening Charge is alive: the two ability charges "
        "of the turn both landed on benched Ogerpon ex, which is what their "
        "own Teal Dance does")


def test_a_ripening_charge_that_did_fire_is_still_billed():
    """The discount is per benched Ogerpon that RECEIVED a Grass. Take those
    away and the estimate goes back to counting every ability charge, which is
    what stops it inventing a route that is gone."""
    obs = _board()
    m.agent(copy.deepcopy(obs))
    m.AGENT_STATE._grass_attach_targets_this_turn = {83}   # only the active
    assert _slots_active(obs) == 0, (
        "with no benched dance to explain them, the turn's two ability charges "
        "are billed here and the capacity of one is spent")
