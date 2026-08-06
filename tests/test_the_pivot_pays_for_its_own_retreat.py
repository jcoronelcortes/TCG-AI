"""The pivot that promised a KO it could not pay for, and the ex it hid.

Scenario (`records/registro_012_pasos_101_hasta_115.json`, step 112, episode
90088766 vs Marnie's Grimmsnarl ex -- game WON, this turn LOST):

    US (3 prizes left)                     RIVAL (6 prizes left)
    active  Teal Mask Ogerpon ex 30/210    active  Marnie's Grimmsnarl ex
            4 Grass                                420/420 (Hero's Cape), 2 Dark
    bench   Meowth ex 170                  bench   Munkidori 110 (1 Dark)
            Fezandipiti ex 120/210                 Marnie's Morpeko 70 (3 Dark)
            Hydrapple ex 330/330, 2 Grass          Marnie's Grimmsnarl ex 320
            Bayleef 110                            Munkidori 110 (1 Dark)
            Applin 40
    hand    -- (the Ultra Ball had just emptied it)

Six Grass on our field. The agent RETREATED the Ogerpon ex, promoted the
Hydrapple ex and attacked. Two separate mistakes, one arithmetic and one
strategic, and the second only happened because of the first.

THE ARITHMETIC. `_hydra_pivot_active` fires when a benched Hydrapple ex knocks
the opposing active out after the retreat. Syrup Storm scales with the TOTAL
Grass ON THE FIELD, and the retreat it is asking for BURNS one of them --
retreat costs are paid by discarding whole energy cards. The projection read the
field BEFORE that discount:

    projected   30 + 30 x 6 = 210, doubled by weakness = 420 >= 420 HP -> "KO"
    actual      30 + 30 x 5 = 180, doubled by weakness = 360 -> they survive on 60

`_retreat_grass_units` exists for exactly this (registro_006 step 78 vs
Archaludon ex, the same overestimate), but it was only subtracted when the body
retreating was ITSELF a Hydrapple. Our active was an Ogerpon, so the discount
never happened.

The phantom KO then pointed `plan.attacker` at the bench, and that SUPPRESSED
the attack of the active -- which was the real thing: Myriad Leaf Shower counts
the energy on BOTH actives, 30 + 30 x (4 + 2) = 210, doubled = 420, the exact
KO of the Grimmsnarl ex for two prizes.

THE HIDDEN EX. What the retreat did instead was tuck a 2-prize ex at 30 HP onto
the bench, in front of two charged Munkidori. Their turn 13 (registro_013):
Adrena-Brain moved 3 counters of the 36 our Syrup Storm had just put on their
Grimmsnarl onto the hidden Ogerpon -- two prizes without attacking, and their
attacker healed 30 in the same motion (60 -> 90 -> 120).

The Tera of a benched Teal Mask Ogerpon ex is why the guard that already
existed said nothing: it cuts the snipe (damage from an ATTACK) and does
nothing against moved counters. And the movable window read 0 because their
four bodies were at full HP -- Adrena-Brain only moves counters that already
exist, and the counters it used were the ones OUR OWN attack was about to put
there. `_movable_dmg_after_our_hit` is that missing term.
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
            / "marnie_t12_the_pivot_pays_the_retreat_step112.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MUNKIDORI = m.Munkidori
GRIMMSNARL = m.Grimmsnarl_ex
MYRIAD_LEAF_SHOWER = 120


@pytest.fixture(autouse=True)
def reset_main_state():
    """The whole of `AGENT_STATE`, not just the card tracking: these fixtures
    are replayed COLD, and the flags of a previous test (the opposing deck
    detected, the plan of the turn) change what the pivots read."""
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _chosen(obs):
    return obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]


def _one_grass_less(obs):
    """The same turn with one Grass fewer on the doomed Ogerpon: Myriad Leaf
    Shower stops being lethal, so the decision moves to the wall pivots."""
    active = obs["current"]["players"][obs["current"]["yourIndex"]]["active"][0]
    active["energies"] = active["energies"][:-1]
    active["energyCards"] = active["energyCards"][:-1]
    return obs


def _without_munkidori(obs):
    cur = obs["current"]
    theirs = cur["players"][1 - cur["yourIndex"]]
    theirs["bench"] = [b for b in theirs["bench"] if b["id"] != MUNKIDORI]
    return obs


# ---------------------------------------------------------------------------
# 1. The board is the one that was recorded
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_that_was_lost():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    active = mine["active"][0]
    assert active["id"] == OGERPON and active["hp"] == 30
    assert len(active["energies"]) == 4

    wall = [b for b in mine["bench"] if b["id"] == HYDRAPPLE][0]
    assert wall["hp"] == wall["maxHp"] and len(wall["energies"]) == 2

    op_active = theirs["active"][0]
    assert op_active["id"] == GRIMMSNARL and op_active["hp"] == 420
    assert len(op_active["energies"]) == 2
    assert sum(1 for b in theirs["bench"] if b["id"] == MUNKIDORI) == 2
    assert all(b["hp"] == b["maxHp"] for b in theirs["bench"]), (
        "their board is untouched: Adrena-Brain has nothing to move YET")

    assert [op["type"] for op in o["select"]["option"]] == [
        int(OptionType.ATTACK), int(OptionType.RETREAT), int(OptionType.END)]


# ---------------------------------------------------------------------------
# 2. The arithmetic: the retreat is paid before the KO is believed
# ---------------------------------------------------------------------------

def test_syrup_storm_is_projected_on_the_field_left_after_the_retreat():
    """Six Grass on the field, one of them burned by the retreat: 360, not 420."""
    o = _obs()
    m.agent(copy.deepcopy(o))          # it fills the tracking of the turn
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    total_grass = sum(len(p["energies"]) for p in mine["active"] + mine["bench"])
    assert total_grass == 6

    cost = m.RETREAT_COST.get(OGERPON, 1)
    after = total_grass - m._retreat_grass_units(cost)
    assert after == 5
    assert 30 + 30 * after == 180                  # x2 weakness = 360
    assert (30 + 30 * after) * 2 < 420, "the Grimmsnarl ex survives the pivot"


def test_the_active_had_the_exact_ko_that_the_pivot_suppressed():
    """Myriad Leaf Shower counts the energy on BOTH actives: 4 + 2."""
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]
    ours = len(mine["active"][0]["energies"])
    theirs_energy = len(theirs["active"][0]["energies"])
    assert (30 + 30 * (ours + theirs_energy)) * 2 == 420 == theirs["active"][0]["hp"]


def test_it_attacks_instead_of_retreating():
    opt = _chosen(_obs())
    assert opt["type"] == int(OptionType.ATTACK)
    assert opt["attackId"] == MYRIAD_LEAF_SHOWER


# ---------------------------------------------------------------------------
# 3. The hidden ex: our own attack is Adrena-Brain's ammunition
# ---------------------------------------------------------------------------

def test_the_movable_window_is_empty_until_we_hit_them():
    o = _obs()
    m.agent(copy.deepcopy(o))
    assert m.AGENT_STATE._op_movable_dmg == 0, (
        "their four bodies are at full HP: nothing to move")
    assert m.AGENT_STATE._op_movable_cap == 60, "two charged Munkidori, 30 each"
    assert m._movable_dmg_after_our_hit(360) == 60, (
        "our Syrup Storm loads their board and the whole ceiling becomes real")


def test_the_30_hp_ex_is_cashable_on_the_bench_after_our_attack():
    o = _obs()
    m.agent(copy.deepcopy(o))
    state = m.to_observation_class(o).current
    ogerpon = state.players[state.yourIndex].active[0]
    op_active = state.players[1 - state.yourIndex].active[0]

    assert not m._bench_cashable_after_retreat(ogerpon, op_active, 0), (
        "before our attack their board is clean and the Tera stops the snipe")
    assert m._bench_cashable_after_retreat(ogerpon, op_active, 360), (
        "after it, 30 moved counters cash the two prizes")


def test_the_wall_pivot_does_not_hide_an_ex_the_munkidori_can_cash():
    """One Grass less: Myriad no longer knocks out, so the wall pivot is the
    play on the table -- and it must not fire while the ex dies down there."""
    opt = _chosen(_one_grass_less(_obs()))
    assert opt["type"] == int(OptionType.ATTACK)


def test_the_same_wall_pivot_still_fires_when_the_bench_is_safe():
    """The guard is narrow: with no Munkidori on their board the hidden ex
    survives (the Tera cuts Shadow Bullet's snipe) and the pivot is right."""
    opt = _chosen(_without_munkidori(_one_grass_less(_obs())))
    assert opt["type"] == int(OptionType.RETREAT)
