"""A finisher the front cannot let through is not a finisher.

Record (user, episode 92595425 step 71, turn 4 vs a Dragapult ex deck, LOST).
Our turn had just assembled the deck's whole engine and the Ripening Charge was
holding the turn's last Grass, asking where to put it:

    US                                        THEM
    active  Hydrapple ex 330/330, ZERO         active  Drakloak 90/90, no energy
            energy, retreat THREE -- it        bench   Drakloak with two energies,
            just evolved this turn                     Budew, Dreepy
    bench   Teal Mask Ogerpon ex with THREE
            Grass, another with TWO, a third
            with ONE, Bayleef, Meowth ex
    hand    Boss's Orders, Unfair Stamp -- and the ONE Grass the ability holds

The turn's manual attachment was already spent, so that Grass was the last one
the turn could move. `_ogerpon_lethal_focus_serial` (main.py) took it: the
benched Ogerpon at two of Myriad Leaf Shower's three would be LETHAL once
charged -- 30 + 30 x (3 + 0) = 120 against a 90 HP Drakloak -- so the focus
priced that body at 41700 and the active Hydrapple ex, at 31210, lost the Grass.

AND THAT OGERPON WAS NEVER GOING TO ATTACK. Promoting it costs a retreat of
three, and the Hydrapple ex in front of it had zero energy: the retreat was
unpayable that turn, and the next one too, because the two charges the turn
after would be spent reaching Syrup Storm's own cost. The Grass went to a body
that could not reach the spot from which the attack is thrown. The turn ended
with no attack, the Hydrapple ex at zero and no Grass left in hand; their
Drakloak evolved into Dragapult ex and Phantom Dive took 200 off our 330.

THE RULE. The focus already carries this idea for ONE case -- its own comment
cites registro_006 step 101 vs Alakazam, where a lethal benched Ogerpon sat
trapped behind an Applin at zero -- but the guard written then only asks whether
the turn is ALREADY planning to pay the retreat (`_ability_unlock_retreat_*`).
That leaves the case where nobody is planning it because it cannot be paid at
all. A benched candidate now has to be REACHABLE: the active must be able to
pay its own retreat with the energy it carries (`_retreat_payable`, whose
docstring is this rule in one line -- "a route that cannot pay its first step is
not a route"). An Ogerpon that IS the active needs no retreat and is untouched.

It is the same test `_ub_usable_attacker` (ptcg/turn/options/card.py) already
makes for the Ultra Ball -- "ready" and "usable" are not the same thing -- moved
to the other decision that needed it. Nothing but our own board goes into it:
a retreat cost, the energy on the body in front. It reads the same against
every deck.

Coverage: the record's board; the boundary in both directions (a front that CAN
step aside keeps the focus, one that cannot loses it); and the active Ogerpon,
which the guard must not touch.
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
from cg.api import AreaType, EnergyType
from golden_corpus import reset_agent
from patching import parcheado

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "dragapult_step71_the_focus_that_cannot_reach_the_front.json")

CHIKORITA = m.Chikorita
GRASS = m.Basic_Grass_Energy
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex

# The band `_ogerpon_lethal_focus_serial` prices its chosen body at
# (ptcg/turn/energy.py). Pinning the number is pinning the rule: no other
# branch of `energy_score` returns it.
FOCUS_BAND = 41700


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


def _scores(obs):
    """The score `energy_score` gave every option of this menu."""
    seen = {}

    def spy(context, select, scores, o, my_index, top_n=3):
        seen["scores"] = list(scores)

    with parcheado("_debug_log_decision", spy):
        m.agent(obs)
    return seen["scores"]


def _bench_index(obs, pokemon_id, energies):
    """Menu index of the benched body with that id and that much energy."""
    mine = _mine(obs)
    for i, o in enumerate(obs["select"]["option"]):
        if o["area"] != int(AreaType.BENCH):
            continue
        body = mine["bench"][o["index"]]
        if body["id"] == pokemon_id and len(body["energies"]) == energies:
            return i
    raise AssertionError(f"no benched {pokemon_id} with {energies} energies")


# ---------------------------------------------------------------------------
# 0. The board is the record's
# ---------------------------------------------------------------------------

def test_the_menu_is_the_ripening_charge_over_a_front_that_cannot_step_aside():
    obs = _board()
    select = obs["select"]
    assert select["effect"]["id"] == HYDRAPPLE, (
        "the select has to be the Hydrapple ex's charging ability")
    assert any(o["area"] == int(AreaType.ACTIVE) for o in select["option"]), (
        "the ACTIVE has to be one of the bodies the ability offers")

    mine = _mine(obs)
    active = mine["active"][0]
    assert active["id"] == HYDRAPPLE and len(active["energies"]) == 0, (
        "the body in front is the Hydrapple ex that just evolved, at zero")
    assert m.RETREAT_COST[HYDRAPPLE] == 3, (
        "the retreat that traps the bench is what this board is about")
    assert sum(1 for b in mine["bench"] if b and b["id"] == OGERPON) == 3

    assert obs["current"]["energyAttached"] is True, (
        "the manual attachment is spent: this Grass is the last one of the turn")

    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    assert op["active"][0]["hp"] == 90, (
        "their 90 HP active is what made the benched Ogerpon read as lethal")


# ---------------------------------------------------------------------------
# 1. The record's board: the trapped body does not take the Grass
# ---------------------------------------------------------------------------

def test_the_charge_does_not_go_to_the_ogerpon_the_front_traps():
    obs = _board()
    option = _decide(obs)
    assert option["area"] == int(AreaType.ACTIVE), (
        "with the retreat unpayable the benched Ogerpon cannot attack from "
        f"anywhere, and the body that will is the one in front; chose {option}")


def test_the_focus_band_is_gone_from_the_trapped_body():
    obs = _board()
    trapped = _bench_index(obs, OGERPON, 2)
    assert _scores(obs)[trapped] != FOCUS_BAND, (
        "the lethal focus must not price a body the front cannot let through")


# ---------------------------------------------------------------------------
# 2. The boundary: what this rule owns, and what it must leave alone
# ---------------------------------------------------------------------------
#
# Same board with a Chikorita in front instead of the Hydrapple ex -- it is not
# in MAIN_ATTACKERS, so it cannot switch the focus off by being viable itself,
# and its retreat costs ONE instead of three.
#
# The pair below is what draws the line. With that one card already on it the
# front can step aside TODAY, the benched Ogerpon is reachable and the focus is
# a real plan. With the front empty the retreat is not unpayable at all -- one
# Grass buys it -- and the turn has a rule for that already
# (`_ability_unlock_retreat_ko`, 41000: charge the front, retreat, promote the
# body that is ALREADY lethal), which switches this whole block off before it
# runs. That is the case this guard must not swallow: the record's board is the
# third one, where the retreat costs three against a front at zero and no
# amount of this turn's charging reaches it.

def _front_is_a_chikorita(obs, energies):
    mine = _mine(obs)
    mine["active"][0] = {
        "appearThisTurn": False,
        "energies": [int(EnergyType.GRASS)] * energies,
        "energyCards": [{"id": GRASS, "playerIndex": 0, "serial": 90 + i}
                        for i in range(energies)],
        "hp": 70, "id": CHIKORITA, "maxHp": 70, "playerIndex": 0,
        "preEvolution": [], "serial": 80, "tools": [],
    }
    return obs


def test_a_front_that_can_step_aside_keeps_the_focus():
    obs = _front_is_a_chikorita(_board(), energies=1)
    trapped = _bench_index(obs, OGERPON, 2)
    assert _scores(obs)[trapped] == FOCUS_BAND, (
        "the Chikorita pays its retreat of one, so the benched Ogerpon can be "
        "promoted and charging it to lethal is a real plan")


def test_a_retreat_the_turn_can_finance_is_not_this_rules_business():
    """One card less on the front, and the answer is NOT this guard.

    A retreat of one against a front at zero is bought by the very Grass we are
    placing, so `_ability_unlock_retreat_ko` takes it at 41000 -- charge the
    front, step aside, promote the Ogerpon that is ALREADY at three -- and that
    flag switches the focus block off before it runs. The guard has nothing to
    say here and must not change it.
    """
    obs = _front_is_a_chikorita(_board(), energies=0)
    scores = _scores(obs)
    active = [i for i, o in enumerate(obs["select"]["option"])
              if o["area"] == int(AreaType.ACTIVE)][0]
    assert scores[active] == 41000, (
        "the retreat-unlock band owns this board, not the lethal focus")
    assert scores[_bench_index(obs, OGERPON, 2)] != FOCUS_BAND


# ---------------------------------------------------------------------------
# 3. An Ogerpon that IS the active needs no retreat
# ---------------------------------------------------------------------------

def test_the_guard_does_not_touch_an_active_ogerpon():
    """The focus can still land on the body in front, which pays no retreat to
    attack from where it already is."""
    obs = _board()
    mine = _mine(obs)
    mine["active"][0] = {
        "appearThisTurn": False,
        "energies": [int(EnergyType.GRASS)] * 2,
        "energyCards": [{"id": GRASS, "playerIndex": 0, "serial": 90 + i}
                        for i in range(2)],
        "hp": 210, "id": OGERPON, "maxHp": 210, "playerIndex": 0,
        "preEvolution": [], "serial": 80, "tools": [],
    }
    option = _decide(obs)
    assert option["area"] == int(AreaType.ACTIVE), (
        "an active Ogerpon one Grass from Myriad Leaf Shower takes it; "
        f"chose {option}")
