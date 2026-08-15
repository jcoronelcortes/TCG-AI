"""Wild Growth pays for the seat's dance, so the charge is EFFECTIVE, not cards.

Scenario (user, `records/registro_011_pasos_069_hasta_079.json` step 79, turn
11, episode 93171867 vs an all-Ogerpon deck, **LOST**). We are `playerIndex 1`.
Their Teal Mask Ogerpon ex had just knocked ours out and the menu asked which
body comes up:

    US (4 prizes)                          RIVAL (2 prizes)
    active  -- just knocked out --         active  **Teal Mask Ogerpon ex
    bench   **Meganium 160, 2e**                   210/210, THREE energies**
            **Teal Mask Ogerpon ex 210, BARE**
            Meowth ex 170, bare
            Tapu Bulu 140, bare
            Applin 40, bare
    hand    Forest of Vitality, Boss's Orders, Bayleef, Applin, **2 Basic Grass**

The line the board offered closes the exchange on our own turn: promote our Teal
Mask Ogerpon ex, draw, dance one Grass onto it and attach the other by hand. Two
CARDS -- but *Wild Growth* is on the bench, so two cards are **four energy**,
which is over Myriad Leaf Shower's cost of three, and the attack counts the
energy on BOTH Active Pokemon ([[ogerpon-myriad-cuenta-ambos-activos]]):
30 + 30 x (4 ours + 3 theirs) = **240 over a 210 HP body**. A Pokemon ex, two
prizes, taken before they can answer.

The agent brought up the **Tapu Bulu**: 140 HP, bare, cost 4 to attack, mute for
at least two turns. `records/registro_012_pasos_080_hasta_086.json` step 80
shows it in the active spot.

WHAT THIS PINS THAT ITS SIBLING DOES NOT
----------------------------------------
The defect itself is the one `test_the_promotion_counts_the_charge_the_seat_unlocks.py`
diagnoses and `PROMOTE_SEAT_UNLOCKS_ITS_CHARGE` fixes: on the bench *Teal Dance*
is dead wood ("if this Pokemon is in the Active Spot"), so every promotion
projection stopped at the manual attachment, the finisher read as MUTE, and the
menu fell through to ordinary survival points where any cheap body outranks an
ex that concedes two prizes. Measured on this board with the switch off, the
ladder is Tapu Bulu 512 > Applin 392 > **Teal Mask Ogerpon ex 293**; with it on
the Ogerpon comes first at 24193.

What is new here is the CORNER of the input space, and it is the corner where a
plausible wrong fix passes its sibling and fails this record:

  * registro_004 step 47 had NO doubler and a candidate already carrying one
    energy -- 1 card = 1 energy, and 1 + 2 charges = the cost exactly;
  * this board has Meganium in play and a candidate at **ZERO** energy -- 2
    cards = 4 energy, and nothing at all without the doubler.

A `_promoted_grass_charges_eff` that returned CARDS instead of multiplying by
`_grass_attach_unit()` would answer 2 here, the Ogerpon would stay one short of
its cost, and this promotion would still be the Tapu Bulu. That multiplication
is the assertion below, taken at both settings of the doubler.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import AreaType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "ogerpon_step079_the_doubler_pays_the_seats_dance.json")

OGERPON = m.Teal_Mask_Ogerpon_ex   # 210 HP, Myriad Leaf Shower: cost 3
MEGANIUM = m.Meganium              # Wild Growth: every Grass counts as two
MEOWTH = m.Meowth_ex
TAPU = m.Tapu_Bulu                 # 140 HP, cost 4 -- the body the agent chose
APPLIN = m.Applin
GRASS = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    yield
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _theirs(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _promoted(obs):
    """The card id the agent brings up out of this TO_ACTIVE menu."""
    choice = m.agent(copy.deepcopy(obs))[0]
    option = obs["select"]["option"][choice]
    assert option["area"] == int(AreaType.BENCH), option
    return _mine(obs)["bench"][option["index"]]["id"]


def _keep_grass(obs, n):
    """Leave exactly `n` basic Grass in hand, everything else untouched."""
    kept, out = 0, []
    for card in _mine(obs)["hand"]:
        if card["id"] == GRASS:
            kept += 1
            if kept > n:
                continue
        out.append(card)
    _mine(obs)["hand"] = out
    _mine(obs)["handCount"] = len(out)


def _pk(card_id, energies=0):
    return SimpleNamespace(id=card_id, energies=[1] * energies,
                           energyCards=[], hp=210, serial=1)


# --- the board itself --------------------------------------------------------

def test_the_board_is_the_one_the_record_lost_on():
    """No assertion below means anything if the fixture drifts."""
    obs = _obs()
    assert obs["current"]["yourIndex"] == 1        # we are the SECOND seat here
    assert not _mine(obs)["active"]                # the promotion is FORCED
    bench = [(b["id"], b["hp"], len(b["energies"])) for b in _mine(obs)["bench"]]
    assert bench == [(MEGANIUM, 160, 2), (OGERPON, 210, 0), (MEOWTH, 170, 0),
                     (TAPU, 140, 0), (APPLIN, 40, 0)]
    assert sum(1 for c in _mine(obs)["hand"] if c["id"] == GRASS) == 2
    rival = _theirs(obs)["active"][0]
    assert (rival["id"], rival["hp"], len(rival["energies"])) == (OGERPON, 210, 3)


def test_the_arithmetic_of_the_seat_lands_over_the_printed_hp():
    """Two CARDS are four energy, and four is what makes the hit lethal."""
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON] == 3
    theirs = 3

    def myriad(ours):
        return 30 + 30 * (ours + theirs)

    assert myriad(2) == 180 < 210    # the manual attachment alone: 2/3, MUTE
    assert myriad(4) == 240 >= 210   # with the dance: over cost, and lethal


def test_the_finisher_comes_up_and_not_the_bare_tapu_bulu():
    assert _promoted(_obs()) == OGERPON


def test_without_the_reading_the_record_repeats_itself():
    """The control arm: the switch off is the build that lost this game."""
    m.PROMOTE_SEAT_UNLOCKS_ITS_CHARGE = False
    try:
        assert _promoted(_obs()) == TAPU
    finally:
        m.PROMOTE_SEAT_UNLOCKS_ITS_CHARGE = True


def test_one_grass_pays_for_one_charge_and_the_body_stays_mute():
    """The rule never invents energy: both routes come out of the SAME hand.

    With a single Grass the dance and the attachment are the same card, two
    effective energy is still under Myriad's three, and the promotion goes back
    to what the record did.
    """
    obs = _obs()
    _keep_grass(obs, 1)
    assert _promoted(obs) == TAPU


# --- the multiplication, at both settings of the doubler ----------------------

def test_the_charge_is_effective_energy_and_not_a_count_of_cards():
    """The corner this record adds to its sibling's, in one assertion.

    Same candidate, same hand, same deficit; the only difference is Wild Growth
    on the bench. A projection that counted CARDS would answer 2 in both rows
    and leave this board's Ogerpon one short of its cost.
    """
    m.AGENT_STATE.meganium_in_play = True
    assert m._grass_attach_unit() == 2
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 0), 2, True, deficit=3) == 4

    m.AGENT_STATE.meganium_in_play = False
    assert m._grass_attach_unit() == 1
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 0), 2, True, deficit=3) == 2


def test_a_bare_candidate_still_needs_both_routes_under_the_doubler():
    """`deficit` is EFFECTIVE too: the manual attachment alone is 2 of 3."""
    m.AGENT_STATE.meganium_in_play = True
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 0), 1, True, deficit=3) == 2      # one card, one route
    assert m._promoted_grass_charges_eff(
        _pk(TAPU, 0), 2, True, deficit=4) == 2         # no ability: no dance
